from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Sequence
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VENDOR_DIR = Path(__file__).resolve().parent / "_vendor"
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))
from core import graph as GRAPH
from core.creator.backup import GRAPH_FILES, _validate_graph_root, has_graph, restore_active_graph
from core.creator.bundle import export_bundle
from core.creator.discovery import discover_tree
from core.creator.intake import DISCOVERY_VERSION, receive_bundle, remove_suites, resolve_suite_root
from core.fsutil import _lock_owner, _process_running, file_lock, iter_files, remove_tree
from core.creator.maintenance import maintain_graph as apply_graph_maintenance
from core.runtime import commands as runtime_commands
from core.runtime.feedback import FeedbackStore, repeated_problems
from core.runtime.registry import Registry


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def import_suite(skill_root: Path, suite_id: str, workspace: Path,
                 skill_ids: set[str] | None = None,
                 exclude_skill_dirs: set[Path] | None = None) -> dict[str, Any]:
    skill_root, workspace = skill_root.resolve(), workspace.resolve()
    skipped: list[dict[str, str]] = []
    with TemporaryDirectory(prefix="labontology-bundle-") as temporary:
        bundle_dir = Path(temporary)
        export_bundle(
            skill_root,
            bundle_dir,
            suite_id,
            include_skill_ids=skill_ids,
            exclude_skill_dirs=exclude_skill_dirs,
            errors=skipped,
            require_contract=True,
        )
        imported = receive_bundle(bundle_dir, workspace, source_root=skill_root)

    cache_dir = Path(imported["output_dir"])
    validation_output = io.StringIO()
    with contextlib.redirect_stdout(validation_output):
        valid = GRAPH.validate(system_dir=cache_dir) == 0
    if not valid:
        raise ValueError(validation_output.getvalue().strip() or "Imported graph is invalid")
    entities, relations = GRAPH.load_graph(cache_dir / "ontology.jsonl")
    if not any(entity.get("type") == "SkillSuite" for entity in entities.values()):
        raise ValueError("Imported graph contains no SkillSuite")
    result = {
        "suite_id": imported["suite_id"],
        "cache_dir": str(cache_dir),
        "skill_count": sum(
            relation.get("relation") == "containsSkill" and relation.get("source") == suite_id
            for relation in relations
        ),
        "validation": {"graphs": 1, "valid": True},
    }
    if skipped:
        result["skipped_workers"] = skipped
    return result


def _brief(text: Any, limit: int = 120) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def inspect_cache(cache_dir: Path, include_skills: bool = False) -> dict[str, Any]:
    cache_dir = cache_dir.resolve()
    registry = Registry.load_cache(cache_dir)
    entities, relations = GRAPH.load_graph(cache_dir / "ontology.jsonl")
    index = json.loads((cache_dir / "source-index.json").read_text(encoding="utf-8"))
    sources = index.get("sources", [])
    missing = sum(not Path(record["path"]).is_file() for record in sources if record.get("path"))
    changed = sum(
        Path(record["path"]).is_file()
        and record.get("sha256") != _sha256(Path(record["path"]))
        for record in sources if record.get("path") and record.get("sha256")
    )
    suites = [{"suite_id": suite.id, "skill_count": len(suite.skills)}
              for suite in sorted(registry.suites.values(), key=lambda suite: suite.id)]
    result = {
        "suites": suites,
        "capabilities": sorted({capability for suite in registry.suites.values()
                                 for capability in suite.available_capabilities}),
        "graph": {"entities": len(entities), "relations": len(relations)},
        "source_integrity": {"records": len(sources), "missing": missing, "changed": changed},
    }
    if len(suites) == 1:
        result.update({"suite_id": suites[0]["suite_id"], "skill_count": suites[0]["skill_count"]})
    if include_skills:
        # Compact Worker inventory, so "what workflows are available" needs no mission.
        inventory = []
        for suite in sorted(registry.suites.values(), key=lambda suite: suite.id):
            for skill_id, spec in sorted(suite.skills.items()):
                knowledge = suite.skill_knowledge.get(skill_id, {})
                item: dict[str, Any] = {"id": skill_id}
                if knowledge.get("name") and knowledge["name"] != skill_id:
                    item["name"] = knowledge["name"]
                item["description"] = _brief(knowledge.get("description"))
                if spec.side_effect_level != "read_only":
                    item["side_effect_level"] = spec.side_effect_level
                inventory.append(item)
        result["skills"] = inventory
    return result


def _workspace_cache_path(workspace: Path) -> Path:
    return workspace.resolve() / "labontology_workspace_cache"


def _default_skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_workspace() -> Path:
    """Use the project root when the command runs from a project-local Skill."""
    current = Path.cwd().resolve()
    skill_dir = _default_skill_dir().resolve()
    skill_parent = skill_dir.parent
    host_dir = skill_parent.parent if skill_parent.name == "skills" else None
    if host_dir is not None and host_dir.name in {".agents", ".agent", ".claude", ".codex"}:
        project_root = host_dir.parent
        if project_root.is_dir() and (current == skill_dir or skill_dir in current.parents):
            return project_root
    return current


def _has_skill_document(root: Path) -> bool:
    try:
        return any(True for _ in iter_files(root, "SKILL.md"))
    except OSError:
        return False


def discover_skill_roots(skill_dir: Path | None = None,
                         workspace: Path | None = None) -> list[Path]:
    """Find visible standard Skill roots without requiring user configuration."""
    anchor = Path(skill_dir or _default_skill_dir()).resolve()
    workspace = Path(workspace or Path.cwd()).resolve()
    configured = os.environ.get("LABONTOLOGY_SKILL_ROOTS", "")
    if configured:
        # An explicit environment setting is an installation-level override.
        # Do not silently add ambient roots from the host project or the
        # LabOntology package itself.
        candidates = [Path(item) for item in configured.split(os.pathsep) if item.strip()]
    else:
        candidates = []
        if anchor.is_dir():
            candidates.append(anchor.parent)

        for relative in (
            Path(".agents") / "skills",
            Path(".agent") / "skills",
            Path(".claude") / "skills",
            Path(".codex") / "skills",
            Path("skills"),
        ):
            candidates.append(workspace / relative)

    roots: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen or not resolved.is_dir() or not _has_skill_document(resolved):
            continue
        seen.add(resolved)
        roots.append(resolved)
    return roots


def _automatic_suite_id(skill_root: Path) -> str:
    digest = hashlib.sha256(str(skill_root.resolve()).encode("utf-8")).hexdigest()[:12]
    return f"suite:auto-{digest}"


def _discover(skill_root: Path, exclude_skill_dirs: set[Path] | None = None,
              errors: list[dict[str, str]] | None = None) -> list[dict[str, Any]]:
    """Release discovery: only declared Workers; unreadable ones are skipped."""
    return discover_tree(skill_root, exclude_skill_dirs=exclude_skill_dirs,
                         errors=errors if errors is not None else [], require_contract=True)


def _worker_skills(skill_root: Path, exclude_skill_dirs: set[Path],
                   errors: list[dict[str, str]] | None = None) -> list[tuple[str, Path]]:
    return [
        (str(skill["id"]), Path(str(skill["source_dir"])).resolve())
        for skill in _discover(skill_root, exclude_skill_dirs, errors)
        if skill.get("id") and skill.get("source_dir")
    ]


def _worker_skill_ids(skill_root: Path, exclude_skill_dirs: set[Path]) -> set[str]:
    return {skill_id for skill_id, _ in _worker_skills(skill_root, exclude_skill_dirs)}


def _cached_skill_owners(cache: Path) -> dict[str, Path]:
    """Map each cached Skill id to the root of the suite that already owns it."""
    roots = _manifest_suite_roots(cache)
    try:
        registry = Registry.load_cache(cache)
    except (OSError, ValueError, KeyError):
        return {}
    owners: dict[str, Path] = {}
    for suite_id in sorted(registry.suites):
        root = roots.get(suite_id)
        if root is not None:
            for skill_id in registry.suites[suite_id].skills:
                owners.setdefault(skill_id, root)
    return owners


def _deduplicate_workers(cache: Path, found: list[tuple[Path, set[Path], list[tuple[str, Path]]]]
                         ) -> tuple[list[tuple[Path, set[Path]]], list[dict[str, str]]]:
    """Import each Worker id once: keep the cached owner, else the first root."""
    cached = _cached_skill_owners(cache)
    owners: dict[str, tuple[Path, Path]] = {}
    for root, _, workers in found:
        for skill_id, source in workers:
            current = owners.get(skill_id)
            if current is None or (cached.get(skill_id) == root and current[0] != root):
                owners[skill_id] = (root, source)
    root_pairs: list[tuple[Path, set[Path]]] = []
    skipped: list[dict[str, str]] = []
    for root, excluded, workers in found:
        duplicates = {source for skill_id, source in workers if owners[skill_id][1] != source}
        skipped.extend({"skill_id": skill_id, "kept": str(owners[skill_id][1]), "skipped": str(source)}
                       for skill_id, source in workers if source in duplicates)
        if any(source not in duplicates for _, source in workers):
            root_pairs.append((root, excluded | duplicates))
    return root_pairs, skipped


# Skills that are their own entry point and are used directly, never as a LabOntology Worker: TRACE Lab's
# closed-loop recommendation (trace-collab-skill) runs through its own tool and project state, and routing it
# through a mission only added a bootstrap and extra calls to every turn.
_SEPARATE_ENTRY_SKILLS = {"trace-collab-skill"}


def _labontology_dirs(skill_root: Path) -> set[Path]:
    excluded = {_default_skill_dir()}
    for skill in _discover(skill_root):
        skill_id = str(skill.get("id") or "").casefold()
        source_dir = Path(str(skill.get("source_dir") or "")).resolve()
        if skill_id in {"labontology", "labontology-skill"} or skill_id in _SEPARATE_ENTRY_SKILLS:
            excluded.add(source_dir)
    return excluded


def _normalise_skill_roots(skill_roots: Sequence[Path]) -> list[Path]:
    roots: list[Path] = []
    seen: set[Path] = set()
    for root in skill_roots:
        resolved = Path(root).resolve()
        if resolved in seen or not resolved.is_dir():
            continue
        seen.add(resolved)
        roots.append(resolved)
    return roots


def _manifest_suite_roots(cache_dir: Path) -> dict[str, Path]:
    """Return each cached SkillSuite's root; relative roots resolve against the workspace."""
    manifest_path = cache_dir / "cache-manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    suite_roots = manifest.get("suite_roots", {}) if isinstance(manifest, dict) else {}
    if not isinstance(suite_roots, dict):
        return {}
    return {str(suite_id): resolve_suite_root(root, cache_dir.parent)
            for suite_id, root in suite_roots.items() if root}


def _cached_suite_roots(cache_dir: Path) -> list[Path]:
    return sorted(set(_manifest_suite_roots(cache_dir).values()))


def _snapshot_graph(cache: Path, snapshot: Path) -> bool:
    """Copy the small graph files (not runs/) so a failed refresh can be undone."""
    if not has_graph(cache):
        return False
    snapshot.mkdir(parents=True)
    for name in GRAPH_FILES:
        shutil.copy2(cache / name, snapshot / name)
    if (cache / ".backup").is_dir():
        shutil.copytree(cache / ".backup", snapshot / ".backup")
    return True


def _restore_graph_snapshot(cache: Path, snapshot: Path, had_graph: bool) -> None:
    remove_tree(cache / ".backup")
    if had_graph:
        for name in GRAPH_FILES:
            os.replace(snapshot / name, cache / name)
        if (snapshot / ".backup").is_dir():
            shutil.copytree(snapshot / ".backup", cache / ".backup")
        return
    for name in GRAPH_FILES:
        (cache / name).unlink(missing_ok=True)
    for folder in (cache / "runs", cache):
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()


# A refresh snapshots the graph into a folder with this prefix and restores it if the refresh fails. A process
# killed part-way (a stopped chat ends bootstrap's command) restores nothing and leaves the folder behind, so the
# next refresh repairs the cache from it first (_recover_interrupted_refresh). owner.pid names the process.
_ROLLBACK_PREFIX = ".labontology-cache-rollback-"
_ROLLBACK_OWNER = "owner.pid"
# A rollback folder counts as abandoned when its owner has ended or, as a lock in file_lock, once it is this
# old (also a folder from before owner.pid was written).
_ROLLBACK_STALE_AFTER = 600.0


def _same_graph_files(cache: Path, snapshot: Path) -> bool:
    try:
        return all(_sha256(cache / name) == _sha256(snapshot / name) for name in GRAPH_FILES)
    except OSError:
        return False


def _recover_interrupted_refresh(workspace: Path, cache: Path) -> str | None:
    """Repair the cache after a refresh whose process was killed part-way: when the cache differs from the
    newest valid snapshot of such a run, restore that snapshot (the refresh that follows brings it up to date
    again), then delete the dead runs' rollback folders. A recent folder whose owner is still running is left
    alone. Returns the name of the folder restored from, if any. Call it under the workspace lock."""
    dead: list[tuple[float, Path]] = []
    for folder in workspace.glob(f"{_ROLLBACK_PREFIX}*"):
        try:
            if not folder.is_dir():
                continue
            created = folder.stat().st_mtime
        except OSError:
            continue
        owner = _lock_owner(folder / _ROLLBACK_OWNER)
        if (time.time() - created > _ROLLBACK_STALE_AFTER
                or (owner is not None and not _process_running(owner))):
            dead.append((created, folder))
    restored = None
    for _, folder in sorted(dead, reverse=True):
        snapshot = folder / "graph"
        if not has_graph(snapshot):
            continue
        try:
            _validate_graph_root(snapshot)
        except ValueError:
            continue
        if has_graph(cache) and _same_graph_files(cache, snapshot):
            break
        cache.mkdir(parents=True, exist_ok=True)
        _restore_graph_snapshot(cache, snapshot, True)
        restored = folder.name
        break
    for _, folder in dead:
        with contextlib.suppress(OSError):
            remove_tree(folder)
    return restored


def ensure_workspace_cache(workspace: Path,
                           skill_roots: Sequence[Path] | None = None) -> dict[str, Any]:
    """Create, reuse, or refresh the one cache for visible Worker Skills."""
    workspace = Path(workspace).resolve()
    cache = _workspace_cache_path(workspace)
    recovered = _recover_interrupted_refresh(workspace, cache)
    automatic = skill_roots is None
    cached_roots = _cached_suite_roots(cache)
    if automatic:
        discovered = discover_skill_roots(workspace=workspace)
        candidates = _normalise_skill_roots([*discovered, *cached_roots])
        anchor = _default_skill_dir().resolve().parent
        # Only scan the anchor when it is a candidate: discovery AST-parses every
        # script below it, which is slow for a large shared Skill library.
        if anchor in candidates:
            anchor_excluded = _labontology_dirs(anchor) if anchor.is_dir() else {_default_skill_dir()}
            if _worker_skill_ids(anchor, anchor_excluded):
                candidates = [anchor, *[root for root in candidates if root in cached_roots and root != anchor]]
    else:
        candidates = _normalise_skill_roots(skill_roots or [])
    skipped_workers: list[dict[str, str]] = []
    found = []
    for root in candidates:
        excluded = _labontology_dirs(root)
        found.append((root, excluded, _worker_skills(root, excluded, skipped_workers)))
    root_pairs, skipped_duplicates = _deduplicate_workers(cache, found)
    if not root_pairs:
        raise ValueError("No visible standard Skill root was found")

    # A cached root that was removed, moved out of reach, or emptied no longer
    # blocks the workspace: its SkillSuites are dropped and reported.
    stale_suites = sorted(
        suite_id for suite_id, root in _manifest_suite_roots(cache).items()
        if root not in {item[0] for item in root_pairs}
    ) if automatic else []

    def sync_root(root: Path, excluded: set[Path]) -> dict[str, Any]:
        explicit = _explicit_suites_for_root(cache, root)
        mapped = explicit or _cached_suites_for_root(cache, root)
        if explicit:
            return sync_workspace_all(root, workspace, exclude_skill_dirs=excluded)
        if mapped:
            return sync_workspace(root, workspace, mapped[0], exclude_skill_dirs=excluded)
        return sync_workspace(
            root,
            workspace,
            _automatic_suite_id(root),
            exclude_skill_dirs=excluded,
        )

    workspace.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=_ROLLBACK_PREFIX, dir=str(workspace)) as temporary:
        (Path(temporary) / _ROLLBACK_OWNER).write_text(f"{os.getpid()}\n", encoding="ascii")
        snapshot = Path(temporary) / "graph"
        had_graph = _snapshot_graph(cache, snapshot)
        try:
            removed_suites = remove_suites(cache, stale_suites) if stale_suites else []
            results = [sync_root(root, excluded) for root, excluded in root_pairs]
        except Exception:
            _restore_graph_snapshot(cache, snapshot, had_graph)
            raise

    manifest_path = cache / "cache-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    synchronized = bool(removed_suites) or any(bool(result.get("synchronized")) for result in results)
    result = {
        "cache_dir": str(cache),
        "roots": [str(root) for root, _ in root_pairs],
        "suite_ids": manifest.get("suite_ids", []),
        "synchronized": synchronized,
        "reused": not synchronized,
        "results": results,
    }
    if removed_suites:
        result["removed_suites"] = removed_suites
    if recovered:
        result["recovered_interrupted_refresh"] = recovered
    if skipped_workers:
        result["skipped_workers"] = skipped_workers
    if skipped_duplicates:
        result["skipped_duplicates"] = skipped_duplicates
    return result


def _cached_suites_for_root(cache_dir: Path, skill_root: Path) -> list[str]:
    exact = _explicit_suites_for_root(cache_dir, skill_root)
    if exact:
        return exact
    index_path = cache_dir / "source-index.json"
    if not index_path.is_file():
        return []
    try:
        sources = json.loads(index_path.read_text(encoding="utf-8")).get("sources", [])
    except (OSError, ValueError, json.JSONDecodeError):
        return []
    return sorted({str(record["suite_id"]) for record in sources
                   if isinstance(record, dict) and record.get("suite_id") and record.get("path")
                   and Path(str(record["path"])).resolve().is_relative_to(skill_root)})


def _explicit_suites_for_root(cache_dir: Path, skill_root: Path) -> list[str]:
    return sorted(suite_id for suite_id, root in _manifest_suite_roots(cache_dir).items()
                  if root == skill_root)


def _library_files(skill_root: Path, skill_ids: set[str] | None = None,
                   exclude_skill_dirs: set[Path] | None = None) -> set[Path]:
    source_dirs = {Path(str(skill["source_dir"])).resolve() for skill in _discover(skill_root, exclude_skill_dirs)
                   if skill_ids is None or str(skill.get("id")) in skill_ids
                   if skill.get("source_dir")}
    # Must match the files recorded by intake (_graph_records) for the subset check.
    return {path.resolve() for source_dir in source_dirs for path in iter_files(source_dir)}


def _suite_skill_ids(cache_dir: Path, suite_id: str) -> set[str]:
    try:
        return set(Registry.load_cache(cache_dir).suite(suite_id).skills)
    except (FileNotFoundError, KeyError, ValueError, OSError, json.JSONDecodeError):
        return set()


def _new_skill_ids(skill_root: Path, cache_dir: Path,
                   exclude_skill_dirs: set[Path] | None = None) -> set[str]:
    discovered = {
        str(skill.get("id")) for skill in _discover(skill_root, exclude_skill_dirs)
        if skill.get("id")
    }
    try:
        known = {skill_id for suite in Registry.load_cache(cache_dir).suites.values() for skill_id in suite.skills}
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError):
        known = set()
    return discovered - known


def _cache_match(cache_dir: Path, skill_root: Path, suite_id: str | None,
                 exclude_skill_dirs: set[Path] | None = None) -> dict[str, Any] | None:
    manifest_path = cache_dir / "cache-manifest.json"
    graph_path = cache_dir / "ontology.jsonl"
    index_path = cache_dir / "source-index.json"
    if not (manifest_path.is_file() and graph_path.is_file() and index_path.is_file()):
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if manifest.get("schema") != "labontology.workspace-cache.v1":
        return None
    if manifest.get("discovery_version") != DISCOVERY_VERSION:
        # Discovery or intake changed since this cache was built: re-import once.
        return None
    suite_ids = manifest.get("suite_ids", [])
    if not isinstance(suite_ids, list) or not all(isinstance(item, str) for item in suite_ids):
        return None
    if suite_id and suite_id not in suite_ids:
        return None
    if suite_id and _manifest_suite_roots(cache_dir).get(suite_id) != skill_root:
        return None
    sources = index.get("sources", [])
    if not isinstance(sources, list):
        return None
    scoped_sources = []
    for record in sources:
        if not isinstance(record, dict) or not record.get("path"):
            continue
        source = Path(str(record["path"])).resolve()
        in_root = source.is_relative_to(skill_root)
        if suite_id:
            if record.get("suite_id") != suite_id or not in_root:
                continue
        elif not in_root:
            continue
        scoped_sources.append((record, source))
    if not scoped_sources:
        return None
    known_paths = {source for _, source in scoped_sources}
    mapped_suites = _explicit_suites_for_root(cache_dir, skill_root)
    expected_skill_ids = _suite_skill_ids(cache_dir, suite_id) if suite_id and len(mapped_suites) > 1 else None
    if not _library_files(skill_root, expected_skill_ids, exclude_skill_dirs).issubset(known_paths):
        return None
    missing_sources = 0
    changed_sources = 0
    for record, source in scoped_sources:
        if not source.is_file():
            missing_sources += 1
        elif not record.get("sha256") or _sha256(source) != record["sha256"]:
            changed_sources += 1
    if missing_sources or changed_sources:
        return None
    validation_output = io.StringIO()
    with contextlib.redirect_stdout(validation_output):
        if GRAPH.validate(system_dir=cache_dir) != 0:
            return None
    return {
        "cache_dir": str(cache_dir),
        "suite_ids": sorted(suite_ids),
        "matched_sources": len(scoped_sources),
        "source_integrity": {"records": len(scoped_sources), "missing": missing_sources, "changed": changed_sources},
        "source_freshness": "current",
    }


def sync_workspace(skill_root: Path, workspace: Path, suite_id: str | None = None,
                   skill_ids: set[str] | None = None, *, propagate_shared: bool = True,
                   exclude_skill_dirs: set[Path] | None = None) -> dict[str, Any]:
    """Refresh one explicit Suite, or safely place unclassified Skills in General."""
    skill_root = skill_root.resolve()
    cache = _workspace_cache_path(workspace)
    matched_suites = _cached_suites_for_root(cache, skill_root)
    new_skill_ids = _new_skill_ids(skill_root, cache, exclude_skill_dirs)
    if suite_id:
        selected_suite = suite_id
    elif len(matched_suites) == 1:
        selected_suite = matched_suites[0]
    elif len(matched_suites) > 1:
        if new_skill_ids:
            # General is an additive bucket: retain its existing members while
            # importing only newly discovered, unclassified Skills.
            existing_general_ids = _suite_skill_ids(cache, "suite:general")
            return sync_workspace(
                skill_root, workspace, "suite:general",
                skill_ids=existing_general_ids | new_skill_ids,
                exclude_skill_dirs=exclude_skill_dirs,
            )
        raise ValueError("Multiple existing SkillSuites own this root; specify --suite-id")
    else:
        selected_suite = "suite:general"
    explicit_mappings = _explicit_suites_for_root(cache, skill_root)
    selected_ids = skill_ids
    if selected_ids is None and len(explicit_mappings) > 1:
        selected_ids = _suite_skill_ids(cache, selected_suite)
    # A requested Skill set that contains IDs absent from the cached Suite is
    # necessarily stale, even if the existing source records still match.
    # This prevents an existing suite:general from incorrectly reusing its old
    # cache when a new unclassified Skill was discovered.
    cached_selected_ids = _suite_skill_ids(cache, selected_suite)
    requested_ids = set(selected_ids or ())
    if requested_ids - cached_selected_ids:
        current = None
    else:
        current = _cache_match(cache, skill_root, selected_suite, exclude_skill_dirs)
    if current is not None:
        return {
            "suite_id": selected_suite,
            "cache_dir": current["cache_dir"],
            "skill_count": len(Registry.load_cache(cache).suite(selected_suite).skills),
            "validation": {"graphs": 1, "valid": True},
            "suite_ids": current["suite_ids"],
            "synchronized": False,
            "reused": True,
        }
    # Skill entities are global in the unified graph. If a changed Skill is
    # shared by multiple Suites rooted at this same library, refresh those
    # memberships together so no Suite keeps an obsolete source hash.
    related_suites: list[str] = []
    if propagate_shared and current is None and selected_suite in explicit_mappings:
        try:
            registry = Registry.load_cache(cache)
            selected_members = set(selected_ids or registry.suite(selected_suite).skills)
            for owner_id in explicit_mappings:
                if owner_id == selected_suite or owner_id not in registry.suites:
                    continue
                if selected_members & set(registry.suite(owner_id).skills):
                    related_suites.append(owner_id)
        except (FileNotFoundError, KeyError, ValueError, OSError, json.JSONDecodeError):
            related_suites = []
    result = import_suite(skill_root, selected_suite, workspace, selected_ids, exclude_skill_dirs)
    for owner_id in related_suites:
        owner_ids = _suite_skill_ids(cache, owner_id)
        import_suite(skill_root, owner_id, workspace, owner_ids, exclude_skill_dirs)
    manifest = json.loads((Path(result["cache_dir"]) / "cache-manifest.json").read_text(encoding="utf-8"))
    return {**result, "suite_ids": manifest["suite_ids"], "synchronized": True, "reused": False,
            **({"related_suites": related_suites} if related_suites else {})}


def sync_workspace_all(skill_root: Path, workspace: Path, *,
                       exclude_skill_dirs: set[Path] | None = None) -> dict[str, Any]:
    skill_root, workspace = skill_root.resolve(), workspace.resolve()
    cache = _workspace_cache_path(workspace)
    suite_ids = _explicit_suites_for_root(cache, skill_root)
    if not suite_ids:
        raise ValueError("--all requires an existing explicit SkillSuite mapping for this root")
    new_skill_ids = _new_skill_ids(skill_root, cache, exclude_skill_dirs)
    results = [sync_workspace(skill_root, workspace, suite_id,
                              skill_ids=_suite_skill_ids(cache, suite_id),
                              propagate_shared=False,
                              exclude_skill_dirs=exclude_skill_dirs) for suite_id in suite_ids]
    if new_skill_ids:
        existing_general_ids = _suite_skill_ids(cache, "suite:general")
        results.append(sync_workspace(
            skill_root, workspace, "suite:general",
            skill_ids=existing_general_ids | new_skill_ids,
            propagate_shared=False,
            exclude_skill_dirs=exclude_skill_dirs,
        ))
    return {"cache_dir": str(_workspace_cache_path(workspace)), "suites": results,
            "synchronized": any(result["synchronized"] for result in results)}


def resolve_cache(skill_root: Path, workspace: Path, suite_id: str | None = None) -> dict[str, Any]:
    skill_root, workspace = skill_root.resolve(), workspace.resolve()
    if not skill_root.is_dir():
        raise ValueError(f"Skill root is unavailable: {skill_root}")
    cache = _workspace_cache_path(workspace)
    selected = _cache_match(cache, skill_root, suite_id, _labontology_dirs(skill_root))
    if selected is None:
        raise ValueError("Workspace cache is unavailable or stale; synchronize the workspace Skill library")
    return {
        "cache_dir": selected["cache_dir"],
        "suite_ids": selected["suite_ids"],
        "suite_id": suite_id if suite_id else selected["suite_ids"][0] if len(selected["suite_ids"]) == 1 else None,
        "candidate_count": 1,
        "matched_sources": selected["matched_sources"],
        "source_integrity": selected["source_integrity"],
    }


def _runtime_result(arguments: list[str]) -> dict[str, Any]:
    rendered = io.StringIO()
    with contextlib.redirect_stdout(rendered):
        runtime_commands.main(arguments)
    return json.loads(rendered.getvalue())


_MISSION_COMMANDS = {"run", "context", "act", "resume", "prepare-skill", "reconcile"}


def _strip_key(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return {k: _strip_key(v, key) for k, v in value.items() if k != key}
    if isinstance(value, list):
        return [_strip_key(item, key) for item in value]
    return value


def _short(text: Any, limit: int) -> Any:
    return text[:limit] + "..." if isinstance(text, str) and len(text) > limit else text


def _slim_action(action: Any) -> Any:
    if not isinstance(action, dict):
        return action
    slim = {key: action.get(key) for key in ("id", "kind", "skill_id", "retry_of", "step_gate", "completed_skill") if action.get(key)}
    for key, limit in (("reason", 200), ("question", 400)):
        if action.get(key):
            slim[key] = _short(action[key], limit)
    if action.get("prepared_skill"):
        slim["prepared_skill"] = {k: action["prepared_skill"].get(k) for k in ("skill_id", "path")}
    return slim


def _compact_result(result: dict[str, Any]) -> dict[str, Any]:
    """Shrink a mission output to what the host Agent needs (state.json on disk is untouched)."""
    result = _strip_key(result, "skill_snapshot")
    mission = result.get("mission")
    if isinstance(mission, dict):
        mission["goal"] = _short(mission.get("goal"), 300)
        mission["decisions"] = [_slim_action(item) for item in mission.get("decisions", [])[-2:]]
        mission["observations"] = [
            {**{k: item.get(k) for k in ("action_id", "status") if item.get(k)},
             "summary": _short(item.get("summary"), 200)} for item in mission.get("observations", [])[-2:]]
        mission["pending_action"] = _slim_action(mission.get("pending_action"))
        mission["pending_ticket"] = _slim_action(mission.get("pending_ticket"))
        mission["action_history"] = mission.get("action_history", [])[-3:]
        executions = {}
        for key, item in (mission.get("skill_executions") or {}).items():
            slim = {k: item.get(k) for k in ("skill_id", "status", "failure_kind", "retryable", "retry_count")
                    if item.get(k) not in (None, [], {})}
            if item.get("outputs"):
                slim["outputs"] = sorted(item["outputs"])  # ids only; the paths are in mission.artifacts
            for text_key, limit in (("summary", 200), ("error", 300)):
                if item.get(text_key):
                    slim[text_key] = _short(item[text_key], limit)
            executions[key] = slim
        mission["skill_executions"] = executions
        mission.pop("artifact_records", None)  # same paths as mission.artifacts
        mission["revisions"] = [{k: v for k, v in item.items() if k != "artifacts_before"}
                                for item in mission.get("revisions", [])[-2:]]
        for noisy in ("available_capabilities", "constraints_digest", "supervisor_status", "mode", "start_skill",
                      "suite_id", "fallback_approval", "untracked_external_calls", "constraints"):
            mission.pop(noisy, None)
    cards = []
    for card in result.get("skills", []):
        slim = {"id": card.get("id"), "description": _short(card.get("description"), 160),
                "match_score": card.get("match_score")}
        for key in ("inputs", "missing_inputs", "missing_capabilities"):
            if card.get(key):
                slim[key] = card[key]
        if card.get("side_effect_level") not in (None, "read_only"):
            slim["side_effect_level"] = card["side_effect_level"]
        if (card.get("optional_script") or {}).get("script_command"):
            slim["script_command"] = card["optional_script"]["script_command"]
        cards.append(slim)
    result["skills"] = cards
    result["workflow_references"] = [{"id": item.get("id"), "skills": item.get("skills")}
                                     for item in result.get("workflow_references", [])]
    result["historical_experiences"] = [{"summary": _short(item.get("summary"), 120)}
                                        for item in result.get("historical_experiences", [])[:2]]
    diagnostic = result.get("coverage_diagnostic") or {}
    result["coverage_diagnostic"] = {k: diagnostic.get(k) for k in ("status", "user_message") if diagnostic.get(k)}
    result["pending_ticket"] = _slim_action(result.get("pending_ticket"))
    for noisy in ("available_capabilities", "start_skill", "candidate_count", "registered_skill_count",
                  "action_history_count", "supervisor_status"):
        result.pop(noisy, None)
    return {key: value for key, value in result.items() if value not in (None, [], {})}


def _render(result: Any, compact: bool) -> str:
    if compact:
        return json.dumps(result, ensure_ascii=False, separators=(", ", ": "))
    return json.dumps(result, ensure_ascii=False, indent=2)


# FounDryClaw runs every conversation of a user in the same workspace, so the missions of all of them share
# one cache. It sets FOUNDRYCLAW_CONVERSATION_ID for each chat; `run` and `resume` record it with the mission,
# so what a new message is assumed to continue (a waiting mission, the recent missions) comes from the same
# conversation. A question asked in another conversation was never seen in this one: it blocked a new
# conversation's `run`, and the model then asked the user that old question again.
CONVERSATION_ENV = "FOUNDRYCLAW_CONVERSATION_ID"
CONVERSATION_FILE = "conversation.json"


def _current_conversation() -> str:
    return os.environ.get(CONVERSATION_ENV, "").strip()


def _record_conversation(cache_dir: Path, mission_id: str) -> None:
    """The conversation that created or last resumed the mission."""
    conversation = _current_conversation()
    run_dir = cache_dir.resolve() / "runs" / mission_id
    if conversation and run_dir.is_dir():
        (run_dir / CONVERSATION_FILE).write_text(json.dumps({"conversation_id": conversation}), encoding="utf-8")


def _in_current_conversation(run_dir: Path) -> bool:
    """True outside FounDryClaw (no conversation id), else only for missions this conversation recorded;
    missions from before conversations were recorded count as another conversation's."""
    conversation = _current_conversation()
    if not conversation:
        return True
    try:
        recorded = json.loads((run_dir / CONVERSATION_FILE).read_text(encoding="utf-8")).get("conversation_id")
    except (OSError, ValueError, AttributeError):
        return False
    return recorded == conversation


def _refuse_run_while_waiting_for_user(cache_dir: Path) -> None:
    """A mission that is waiting for the user's answer is almost always what the next message continues.

    Creating a second mission then loses the first one's uploaded inputs and the confirmed plan, so
    `run` refuses until the caller either resumes that mission or explicitly passes --new-mission.
    Only this conversation's missions count (see CONVERSATION_ENV)."""
    runs_dir = cache_dir.resolve() / "runs"
    if not runs_dir.is_dir():
        return
    waiting = []
    for state_path in runs_dir.glob("*/state.json"):
        if not _in_current_conversation(state_path.parent):
            continue
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if state.get("status") == "waiting_human":
            ticket = state.get("pending_ticket") or {}
            waiting.append((state_path.stat().st_mtime, state.get("mission_id", state_path.parent.name),
                            str(ticket.get("question") or state.get("block_reason") or "")))
    if not waiting:
        return
    _, mission_id, question = max(waiting)
    raise ValueError(
        f"Mission {mission_id} is still waiting for the user's answer to: {question[:200]!r}. "
        "If the user's latest message answers or confirms that, do not create a new mission: continue it with "
        f"`resume --cache-dir {cache_dir} --mission-id {mission_id} --answer \"<the user's exact message>\"` "
        "(add --confirm or --reject for an approval). Only when the message is clearly a different, unrelated "
        "goal, run again with --new-mission.")


def _canonical_input_arguments(cache_dir: Path, items: list[str]) -> tuple[list[str], dict[str, str]]:
    """Give an input file the artifact id a Worker declares for it.

    `parsed_constraints.json=...` becomes also `artifact:parsed-constraints=...` when some registered Worker
    declares that input, so a follow-up mission can reuse earlier results without guessing ids. The original
    name is kept as well."""
    try:
        registry = Registry.load_cache(cache_dir)
    except (OSError, ValueError, KeyError):
        return items, {}
    declared = {artifact for suite in registry.suites.values() for spec in suite.skills.values()
                for artifact in spec.input_artifacts}
    result, mapped = list(items), {}
    present = {item.partition("=")[0] for item in items}
    for item in items:
        name, separator, path = item.partition("=")
        if not separator or name in declared:
            continue
        stem = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", name.removeprefix("artifact:"))
        stem = re.sub(r"[_-]?\d{6,}(?:[_-]\d+)?$", "", stem)
        key = "artifact:" + re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
        for candidate in (key, key[:-1] if key.endswith("s") else key):
            if candidate in declared and candidate not in present:
                result.append(f"{candidate}={path}")
                mapped[name] = candidate
                present.add(candidate)
                break
    return result, mapped


def run_mission(cache_dir: Path, goal: str, mission_id: str | None, suite_id: str | None,
                input_artifacts: list[str], constraints: list[str] | None = None,
                new_mission: bool = False, plan: str = "",
                run_through: bool = False) -> dict[str, Any]:
    if not new_mission:
        _refuse_run_while_waiting_for_user(cache_dir)
    mission_id = mission_id or uuid4().hex
    arguments = [
        "run", "--system-dir", str(cache_dir.resolve()), "--mission-id", mission_id, "--goal", goal,
    ]
    if suite_id:
        arguments.extend(["--suite", suite_id])
    if plan.strip():
        arguments.extend(["--plan", plan.strip()])
    if run_through:
        arguments.append("--run-through")
    for constraint in constraints or []:
        arguments.extend(["--constraint", constraint])
    input_artifacts, mapped_inputs = _canonical_input_arguments(cache_dir, input_artifacts)
    for artifact in input_artifacts:
        arguments.extend(["--input-artifact", artifact])
    result = _runtime_result(arguments)
    _record_conversation(cache_dir, mission_id)
    if mapped_inputs:
        result["input_ids"] = mapped_inputs
    return {"mission_id": mission_id, **result}


def mission_context(cache_dir: Path, mission_id: str, suite_id: str | None = None) -> dict[str, Any]:
    arguments = ["context", "--system-dir", str(cache_dir.resolve()), "--mission-id", mission_id]
    if suite_id:
        arguments.extend(["--suite", suite_id])
    return _runtime_result(arguments)


def _plan_question(cache_dir: Path, mission_id: str, suite_id: str | None) -> str:
    progress = mission_context(cache_dir, mission_id, suite_id).get("plan_progress") or []
    if not progress:
        raise ValueError("This mission has no --plan; create it with `run --plan id1,id2,...` or use --ask")
    lines = [f"{index}）{item['skill_id']}：{item.get('description') or ''}".rstrip("：")
             for index, item in enumerate(progress, 1)]
    return ("请确认按以下顺序逐步执行（每完成一个步骤会先展示结果，等你确认后再进行下一步；全程不提交设备）：\n" + "\n".join(lines) + "\n是否确认？")


def act_shortcut(cache_dir: Path, mission_id: str, args: argparse.Namespace) -> dict[str, Any]:
    """Build the decision file for the host Agent (no hand-written JSON), then submit it."""
    suite_id = args.suite_id
    if args.skill:
        _prepare_fresh(cache_dir, mission_id, args.skill, suite_id)  # records the Worker document
        decision: dict[str, Any] = {
            "kind": "skill", "skill_id": args.skill,
            "reason": args.reason or f"Run {args.skill}, the next step of the confirmed plan.",
            "assessment": {"impact": "routine", "rationale": args.reason or f"{args.skill} works on the mission inputs.",
                           "uncertainties": [], "authenticity_gaps": []},
        }
        if args.retry_of:
            decision["retry_of"] = args.retry_of
        inputs = _worker_inputs(args.input)
        if inputs:
            decision["inputs"] = inputs
    elif args.ask or args.ask_plan:
        question = args.ask or _plan_question(cache_dir, mission_id, suite_id)
        decision = {"kind": "request_human", "reason": args.reason or "The user must confirm or supply this.",
                    "question": question}
    elif args.complete:
        decision = {"kind": "complete", "reason": args.reason or "All results are recorded by the Runtime."}
    else:
        decision = {"kind": "cancel", "reason": args.reason or "The user stopped the task."}
    decision_file = cache_dir.resolve() / "runs" / mission_id / "decision.json"
    decision_file.parent.mkdir(parents=True, exist_ok=True)
    decision_file.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    result = act_mission(cache_dir, mission_id, decision_file, suite_id)
    if args.skill:
        _raise_if_worker_blocked(result, args.skill, cache_dir, mission_id)
    return result


def _worker_inputs(items: list[str] | None) -> dict[str, str]:
    """act --skill X --input ARTIFACT_ID=PATH: input files for the Worker that the mission does not hold yet
    (for example a file the user uploaded after the mission started)."""
    inputs: dict[str, str] = {}
    for item in items or []:
        artifact_id, separator, path = item.partition("=")
        if not separator or not artifact_id.strip() or not path.strip():
            raise ValueError(f"--input needs ARTIFACT_ID=PATH (for example artifact:parsed-constraints=<file>), got {item!r}")
        inputs[artifact_id.strip()] = str(Path(path.strip().strip("\"'")).expanduser().resolve())
    return inputs


def _raise_if_worker_blocked(result: dict[str, Any], skill_id: str, cache_dir: Path, mission_id: str) -> None:
    """The Runtime records a Worker it could not start (an input or capability missing) as a "blocked"
    observation and goes back to choosing; reported as success, that left a model retrying blindly. Say what
    is missing and how to give it."""
    mission = result.get("mission") or {}
    decisions = [d for d in mission.get("decisions") or [] if isinstance(d, dict) and d.get("skill_id") == skill_id]
    if not decisions:
        return
    action_id = decisions[-1].get("id")
    blocked = next((o for o in reversed(mission.get("observations") or [])
                    if isinstance(o, dict) and o.get("action_id") == action_id and o.get("status") == "blocked"), None)
    if not blocked:
        return
    summary = str(blocked.get("summary") or "the Worker could not start")
    message = f"{skill_id} was not started: {summary}."
    missing = re.search(r"Required inputs missing: \[(.*)\]", summary)
    if missing:
        ids = [part.strip().strip("'\"") for part in missing.group(1).split(",") if part.strip()]
        message += (
            " Give each missing input as a file: python .claude/skills/labontology/scripts/labontology.py act "
            f"--cache-dir {cache_dir.name} --mission-id {mission_id} --skill {skill_id} "
            + " ".join(f"--input {artifact}=<path of that file>" for artifact in ids)
            + ". A file the user uploaded counts (its path is in the message's attachment list); ask the user only "
              "if no such file was given."
        )
    raise ValueError(message)


def revise_mission(cache_dir: Path, mission_id: str, change: str, redo: str,
                   suite_id: str | None = None) -> dict[str, Any]:
    """Reopen a finished mission for the user's change; only the listed Workers run again."""
    arguments = ["revise", "--system-dir", str(cache_dir.resolve()), "--mission-id", mission_id,
                 "--change", change, "--redo", redo]
    if suite_id:
        arguments.extend(["--suite", suite_id])
    return _runtime_result(arguments)


def _reason_into_decision_file(decision_file: Path, reason: str) -> None:
    """act --decision-file <file> --reason "...": the Runtime reads the reason from the file only, so a
    --reason given on the command line is written into a decision that has none (a model once passed
    --reason three times and got "Decision requires a reason" each time)."""
    if not (reason or "").strip():
        return
    try:
        decision = json.loads(decision_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return  # the Runtime reports the unreadable file
    if not isinstance(decision, dict) or str(decision.get("reason") or "").strip():
        return
    decision["reason"] = reason.strip()
    decision_file.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")


def act_mission(cache_dir: Path, mission_id: str, decision_file: Path,
                suite_id: str | None = None) -> dict[str, Any]:
    arguments = ["act", "--system-dir", str(cache_dir.resolve()), "--mission-id", mission_id,
                 "--decision-file", str(decision_file.resolve())]
    if suite_id:
        arguments.extend(["--suite", suite_id])
    return _runtime_result(arguments)


def reconcile_mission(cache_dir: Path, mission_id: str, outcome: str, summary: str,
                      *, suite_id: str | None = None,
                      evidence: list[str] | None = None,
                      provided_artifacts: list[str] | None = None) -> dict[str, Any]:
    arguments = ["reconcile", "--system-dir", str(cache_dir.resolve()),
                 "--mission-id", mission_id, "--outcome", outcome, "--summary", summary]
    if suite_id:
        arguments.extend(["--suite", suite_id])
    for item in evidence or []:
        arguments.extend(["--evidence", item])
    for item in provided_artifacts or []:
        arguments.extend(["--provide-artifact", item])
    return _runtime_result(arguments)


def prepare_mission_skill(cache_dir: Path, mission_id: str, skill_id: str,
                          suite_id: str | None = None) -> dict[str, Any]:
    arguments = ["prepare-skill", "--system-dir", str(cache_dir.resolve()),
                 "--mission-id", mission_id, "--skill-id", skill_id]
    if suite_id:
        arguments.extend(["--suite", suite_id])
    return _runtime_result(arguments)


_STALE_DOCUMENT = "Skill document changed; refresh the cache"


def _prepare_fresh(cache_dir: Path, mission_id: str, skill_id: str,
                   suite_id: str | None = None) -> dict[str, Any]:
    """prepare-skill; a Worker document edited after the cache was built is refreshed once (as bootstrap does)
    instead of failing in the middle of a mission, where the Agent is told not to run bootstrap."""
    try:
        return prepare_mission_skill(cache_dir, mission_id, skill_id, suite_id)
    except ValueError as exc:
        if _STALE_DOCUMENT not in str(exc):
            raise
    # The workspace lock, as bootstrap takes it: one graph writer at a time.
    workspace = cache_dir.resolve().parent
    with file_lock(workspace / ".labontology_workspace_cache.lock"):
        ensure_workspace_cache(workspace, None)
    return prepare_mission_skill(cache_dir, mission_id, skill_id, suite_id)


def restore_backup(cache_dir: Path) -> dict[str, Any]:
    return restore_active_graph(cache_dir)


def suggest_maintenance(cache_dir: Path, threshold: int = 3,
                        skill_id: str | None = None) -> dict[str, Any]:
    # Runtime records feedback beside the missions, under <cache>/runs.
    feedback = FeedbackStore(cache_dir / "runs").aggregate(skill_id=skill_id)
    return {"threshold": threshold, "suggestions": repeated_problems(feedback, threshold)}


def maintain_graph(cache_dir: Path, patch_file: Path, reason: str) -> dict[str, Any]:
    patch = json.loads(patch_file.read_text(encoding="utf-8-sig"))
    return apply_graph_maintenance(cache_dir, patch, reason)


def mission_status(cache_dir: Path, mission_id: str) -> dict[str, Any]:
    return _runtime_result([
        "status", "--runs-dir", str(cache_dir.resolve() / "runs"), "--mission-id", mission_id,
    ])


def _register_all_artifacts(cache_dir: Path, mission_id: str, explicit: list[str]) -> list[str]:
    """--provide-artifact list covering every unregistered file the Worker wrote into the mission artifact folder."""
    run_dir = cache_dir.resolve() / "runs" / mission_id
    try:
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unknown mission: {mission_id}") from exc
    known = {Path(value).resolve() for value in (state.get("artifacts") or {}).values() if isinstance(value, str)}
    known.update(Path(rec["path"]).resolve() for rec in (state.get("artifact_records") or {}).values()
                 if isinstance(rec, dict) and rec.get("path"))
    provided_paths = {Path(item.partition("=")[2]).resolve() for item in explicit}
    artifacts_dir = run_dir / "artifacts"
    # Only this round's folder (artifacts/rev<N>/ during a revision): a file another round left behind is not
    # an output of the pending Worker.
    revisions = state.get("revisions") or []
    round_dir = artifacts_dir / f"rev{len(revisions)}" if revisions else artifacts_dir
    remaining = [path for path in sorted(round_dir.rglob("*"))
                 if path.is_file() and path.resolve() not in known and path.resolve() not in provided_paths
                 and (revisions or not re.fullmatch(r"rev\d+", path.relative_to(artifacts_dir).parts[0]))]
    pending_id = (state.get("pending_action") or {}).get("id")
    execution = (state.get("skill_executions") or {}).get(pending_id) or {}
    required = list(execution.get("required_outputs") or [])
    templates = execution.get("output_templates") or {}
    if not remaining and not explicit:
        if not required:
            return []  # a Worker without declared output files (e.g. one that works through a tool): nothing to register
        raise ValueError(f"No unregistered files found in {round_dir}; write the Worker outputs there first")
    have = {item.partition("=")[0].removeprefix("artifact:") for item in explicit}
    result = list(explicit)

    def norm(text: str) -> str:
        return re.sub(r"[^a-z0-9]", "", text.lower())

    missing = [name for name in required if name.removeprefix("artifact:") not in have]
    for name in missing:
        key = norm(name.removeprefix("artifact:"))
        matches = [path for path in remaining if norm(path.stem).startswith(key)]
        if not matches:
            suffix = Path(str(templates.get(name, ""))).suffix.lower()
            same_kind = [path for path in remaining if suffix and path.suffix.lower() == suffix]
            if len(missing) == 1 and same_kind:
                matches = same_kind  # the Worker's single declared output, whatever the file was named
            elif len(same_kind) == 1:
                matches = same_kind
            elif len(missing) == 1 and len(remaining) == 1:
                matches = list(remaining)
        if matches:
            chosen = max(matches, key=lambda path: path.stat().st_mtime)
            result.append(f"{name}={chosen}")
            remaining.remove(chosen)
    used = {item.partition("=")[0].removeprefix("artifact:") for item in result} | {
        key.removeprefix("artifact:") for key in (state.get("artifacts") or {})}
    for path in remaining:
        base = re.sub(r"[^A-Za-z0-9]+", "-", path.stem).strip("-").lower() or "file"
        name, number = base, 2
        while name in used:
            name, number = f"{base}-{number}", number + 1
        used.add(name)
        result.append(f"artifact:{name}={path}")
    return result


def resume_mission(cache_dir: Path, mission_id: str, *, suite_id: str | None = None,
                   action_id: str = "", status: str | None = None,
                   confirm: bool = False, reject: bool = False,
                   answer: str = "", summary: str = "", evidence: list[str] | None = None,
                   provided_artifacts: list[str] | None = None, agent_completed: bool = False,
                   agent_failed: bool = False, register_all: bool = False) -> dict[str, Any]:
    if answer.lstrip().startswith("Base directory for this skill") or "\n# LabOntology" in answer:
        raise ValueError(
            "That text is the system's skill-loading note, not the user's message, so it cannot be recorded as an "
            "answer or a confirmation. Ask the user the pending question and end the turn; the reply arrives in "
            "the user's next message.")
    if register_all:
        provided_artifacts = _register_all_artifacts(cache_dir, mission_id, provided_artifacts or [])
    arguments = ["resume", "--system-dir", str(cache_dir.resolve()), "--mission-id", mission_id]
    if suite_id:
        arguments.extend(["--suite", suite_id])
    if action_id:
        arguments.extend(["--action-id", action_id])
    if status:
        arguments.append("--agent-completed" if status == "succeeded" else "--agent-failed")
    for flag, enabled in (("--confirm", confirm), ("--reject", reject),
                          ("--agent-completed", agent_completed), ("--agent-failed", agent_failed)):
        if enabled:
            arguments.append(flag)
    if answer:
        arguments.extend(["--answer", answer])
    if summary:
        arguments.extend(["--summary", summary])
    for item in evidence or []:
        arguments.extend(["--evidence", item])
    for item in provided_artifacts or []:
        arguments.extend(["--provide-artifact", item])
    result = _runtime_result(arguments)
    _record_conversation(cache_dir, mission_id)  # continuing it here makes it this conversation's mission
    return result


def _select_skill(registry: Registry, skill_id: str, suite_id: str | None = None):
    if suite_id:
        try:
            suite = registry.suite(suite_id)
        except KeyError as exc:
            raise ValueError(f"Unknown SkillSuite: {suite_id}") from exc
        skill = suite.skills.get(skill_id)
        if skill is None:
            raise ValueError(f"Unknown Skill in {suite_id}: {skill_id}")
        return suite, skill
    matches = [(suite, suite.skills[skill_id]) for suite in registry.suites.values() if skill_id in suite.skills]
    if not matches:
        raise ValueError(f"Unknown Skill: {skill_id}")
    if len(matches) != 1:
        raise ValueError(f"Skill {skill_id} belongs to multiple SkillSuites; specify --suite-id")
    return matches[0]


def describe_skill(cache_dir: Path, skill_id: str, suite_id: str | None = None) -> dict[str, Any]:
    suite, skill = _select_skill(Registry.load_cache(cache_dir.resolve()), skill_id, suite_id)
    knowledge = suite.skill_knowledge.get(skill.id, {})
    return {
        "id": skill.id,
        "suite_id": suite.id,
        "name": knowledge.get("name", skill.id),
        "description": knowledge.get("description"),
        "inputs": list(skill.input_artifacts),
        "outputs": dict(skill.outputs),
        "required_capabilities": list(skill.required_capabilities),
        "side_effect_level": skill.side_effect_level,
        "optional_command": list(skill.optional_command),
        "optional_entrypoints": list(skill.optional_entrypoints),
        "instruction_source": knowledge.get("instruction_source"),
        "documentation": knowledge.get("documentation", {}),
        "unresolved": knowledge.get("unresolved", []),
        "evidence": knowledge.get("evidence", []),
        "capability_evidence": knowledge.get("capability_evidence", []),
        "contract_evidence": knowledge.get("contract_evidence", []),
        "preconditions": knowledge.get("preconditions", []),
        "decision_policy": knowledge.get("decision_policy", {}),
    }


def list_missions(cache_dir: Path, query: str | None = None) -> dict[str, Any]:
    runs_dir = cache_dir.resolve() / "runs"
    needle = (query or "").casefold()
    missions = []
    for state_path in sorted(runs_dir.glob("*/state.json")) if runs_dir.is_dir() else []:
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        goal = str(state.get("goal", ""))
        if needle and needle not in goal.casefold() and needle not in str(state.get("mission_id", "")).casefold():
            continue
        missions.append({"mission_id": state.get("mission_id", state_path.parent.name), "goal": goal,
                         "status": state.get("status", "unknown"), "suite_id": state.get("suite_id")})
    return {"missions": missions}


# --- repeat guard -----------------------------------------------------------------
# A host Agent that cannot decide what to do next tends to re-run the same read-only
# command (bootstrap / context ...) dozens of times, burning tokens while the mission
# state never changes. Track read-only calls per working directory and refuse the call
# that repeats too often with no state-changing command in between.
_READ_ONLY_COMMANDS = {"bootstrap", "context", "status", "inspect", "describe-skill", "missions",
                       "resolve-cache", "suggest-maintenance"}
_BOOTSTRAP_LIMIT = 2       # bootstrap runs allowed per window, whatever happened in between
_REPEAT_WINDOW_SECONDS = 600  # ... within this window, without a state-changing command
_DIGEST_FROM = 3            # from this repeat on, `context` returns a short digest instead of the full output
_RESUME_WINDOW_SECONDS = 60  # an identical `resume` inside this window is a repeat


_LAST_REPEAT_COUNT = 0  # repeat number of the current read-only call (set by _repeat_guard)


def _repeat_guard_path() -> Path:
    from tempfile import gettempdir
    key = hashlib.sha256(str(Path.cwd().resolve()).encode("utf-8")).hexdigest()[:16]
    return Path(gettempdir()) / f"labontology_repeat_guard_{key}.json"


def _repeat_guard(args: argparse.Namespace) -> dict[str, Any] | None:
    """Record this call; refuse only what can never help.

    - `bootstrap` after two runs is skipped (the cache is unchanged; exit 0).
    - The very same `resume` sent again within a minute is refused (it was recorded the first time).
    - Repeated read-only calls are never refused: from the 3rd repeat `context` returns a short digest
      that still holds everything needed to proceed (see _context_digest)."""
    import time
    global _LAST_REPEAT_COUNT
    path = _repeat_guard_path()
    now = time.time()
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    boots = [at for at in state.get("boots", []) if now - at <= _REPEAT_WINDOW_SECONDS]
    result = None
    if args.command == "bootstrap":
        cache = _workspace_cache_path(args.workspace or _default_workspace())
        if len(boots) >= _BOOTSTRAP_LIMIT and (cache / "cache-manifest.json").is_file():
            state["boots"] = boots
            _write_guard_state(path, state)
            skipped = {"bootstrap_skipped": True, "reused": True, "cache_dir": str(cache),
                       "message": ("bootstrap already ran for this workspace; the cache is ready and unchanged. "
                                   "Do not run bootstrap again this turn - continue with the next step "
                                   "(`active_missions` shows the recent missions and what each needs next).")}
            missions = _active_missions(cache)
            if missions:
                skipped["active_missions"] = missions
            return skipped
        boots.append(now)
    elif args.command == "resume":
        signature = "resume:" + json.dumps([getattr(args, "mission_id", ""), getattr(args, "action_id", ""),
                                            getattr(args, "answer", ""), bool(getattr(args, "confirm", False)),
                                            bool(getattr(args, "reject", False))], ensure_ascii=False)
        recent = [item for item in state.get("resumes", []) if now - item["at"] <= _RESUME_WINDOW_SECONDS]
        count = sum(1 for item in recent if item["sig"] == signature) + 1
        state["resumes"] = recent + [{"sig": signature, "at": now}]
        if count > 2:
            result = {"repeat_guard": True, "command": "resume", "repeat_count": count,
                      "message": ("This exact `resume` was already sent " + str(count - 1) +
                                  " times; it was recorded the first time and repeating it changes nothing."),
                      "next": _guard_next_step(args)}
    elif args.command in _READ_ONLY_COMMANDS:
        signature = f"{args.command}:{getattr(args, 'mission_id', '') or ''}"
        recent = [item for item in state.get("calls", []) if now - item["at"] <= _REPEAT_WINDOW_SECONDS]
        _LAST_REPEAT_COUNT = sum(1 for item in recent if item["sig"] == signature) + 1
        state["calls"] = recent + [{"sig": signature, "at": now}]
    else:
        state = {}  # run / act / reconcile / prepare-skill ... changed something: counts reset
    state["boots"] = boots
    _write_guard_state(path, state)
    return result


def _active_missions(cache: Path, limit: int = 3) -> list[dict[str, Any]]:
    """This conversation's recent missions (updated within a day) with their status and next step, for a
    skipped bootstrap. `missions` still lists every mission in the workspace."""
    import time
    runs = cache / "runs"
    if not runs.is_dir():
        return []
    now = time.time()
    paths = sorted((path for path in runs.glob("*/state.json")
                    if now - path.stat().st_mtime <= 86400 and _in_current_conversation(path.parent)),
                   key=lambda path: path.stat().st_mtime, reverse=True)[:limit]
    missions = []
    for path in paths:
        try:
            context = mission_context(cache, path.parent.name)
        except Exception:  # noqa: BLE001 - a broken mission must not break bootstrap
            continue
        mission = context.get("mission") or {}
        missions.append({"mission_id": path.parent.name, "status": mission.get("status"),
                         "goal": _short(mission.get("goal"), 80), "do_next": (context.get("do_next") or [""])[0]})
    return missions


def _guard_next_step(args: argparse.Namespace) -> str:
    """What to do instead of re-reading the same state, from the mission's recorded status."""
    status = ""
    cache, mission = getattr(args, "cache_dir", None), getattr(args, "mission_id", None)
    if cache and mission:
        try:
            status = json.loads((Path(cache) / "runs" / mission / "state.json").read_text(encoding="utf-8")).get("status", "")
        except (OSError, json.JSONDecodeError):
            pass
    hints = {
        "awaiting_decision": ("You already have this mission's context in the conversation. Now pick one Worker from "
                              "its `skills`, Read that Worker's SKILL.md, run `prepare-skill`, write decision.json, "
                              "run `act`. If no Worker fits or an input is missing, tell the user and end the turn."),
        "waiting_agent": ("A Worker action is issued: follow the prepared Worker SKILL.md (run its script if it "
                          "declares one), then `resume --agent-completed` (or `--agent-failed` with the real error) "
                          "including every file written to the artifacts folder."),
        "waiting_human": ("If the user's latest message answers or confirms `pending_ticket.question`, run "
                          "`resume --answer \"<their exact message>\"` now (add --confirm/--reject for an approval); "
                          "otherwise relay the question and end the turn."),
        "completed": "The mission is completed: report the recorded result and end the turn.",
        "cancelled": "The mission is cancelled: tell the user and end the turn.",
    }
    if args.command == "resume" and status == "waiting_human":
        # The same answer sent again is not the user's reply to the question that is open now.
        hints["waiting_human"] = ("The open question in `pending_ticket.question` has not been answered by the user "
                                  "yet. Do not run resume again in this turn: write your reply now (show the result of "
                                  "the finished step, ask that question) and end the turn.")
    return (hints.get(status, "Decide from the context you already have.") +
            " Do not call bootstrap/context/status again; if you cannot proceed, reply to the user with what is "
            "finished, what blocks the next step and what you need.")


def _context_digest(result: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Short replacement for a repeated `context`: state, plan progress and the exact next commands."""
    mission = result.get("mission", {})
    pending = mission.get("pending_action") or {}
    digest: dict[str, Any] = {
        "context_digest": True,
        "note": (f"`context` repeated {_LAST_REPEAT_COUNT} times with no state-changing command in between: "
                 "short digest of the unchanged state. Do what `do_next` says."),
        "mission_id": args.mission_id,
        "status": mission.get("status"),
        "plan_progress": result.get("plan_progress"),
        "do_next": result.get("do_next"),
        "candidates": [{"id": item.get("id"), "missing_inputs": item.get("missing_inputs", [])}
                       for item in result.get("skills", [])],
        "artifacts": mission.get("artifacts"),
        "artifact_dir": result.get("artifact_dir"),
    }
    if pending:
        digest["pending"] = {"id": pending.get("id"), "kind": pending.get("kind"), "skill_id": pending.get("skill_id")}
        digest["prepared_skill"] = result.get("prepared_skill")
        digest["question_for_user"] = (result.get("pending_ticket") or {}).get("question")
    for decision in reversed(mission.get("decisions", [])):
        if decision.get("kind") == "request_human" and decision.get("question"):
            digest["last_question_to_user"] = decision["question"]
            break
    return {key: value for key, value in digest.items() if value not in (None, [], {})}


def _write_guard_state(path: Path, state: dict[str, Any]) -> None:
    try:
        path.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass


def _user_facing_error(exc: Exception) -> str:
    """Translate common release errors into experiment-language guidance."""
    message = str(exc)
    translations = (
        ("No visible standard Skill root was found",
         "没有找到可见的标准 Skill 目录，请确认实验 Worker Skill 已正常安装。"),
        ("Unknown mission:", "没有找到这个任务："),
        ("workspace cache is incomplete:",
         "实验流程库文件不完整，可以先执行 restore-backup 恢复："),
        ("Another LabOntology command is still running:",
         "另一个 LabOntology 操作仍在进行，请稍后再试："),
        ("Workspace cache is unavailable or stale; synchronize the workspace Skill library",
         "实验流程库需要更新，请先同步后再继续。"),
        ("Multiple existing SkillSuites own this root; specify --suite-id",
         "这个 Skill 目录对应多个实验流程集合，请明确要使用的实验项目。"),
        ("--all requires an existing explicit SkillSuite mapping for this root",
         "只有已经登记过实验项目的 Skill 目录才能执行全量维护。"),
        ("Mission belongs to a different SkillSuite",
         "这个任务属于另一个实验项目，请继续使用任务原本所属的项目。"),
        ("Unknown Skill:", "没有找到匹配的实验步骤："),
        ("Unknown Skill in", "当前实验项目中没有找到这个实验步骤："),
        ("Required inputs missing:", "执行前还缺少必要输入："),
        ("Required capability unavailable:", "执行前还缺少必要能力："),
    )
    for source, target in translations:
        if message.startswith(source):
            suffix = message[len(source):].lstrip()
            return f"{target}{suffix}" if suffix else target
    return message


def _graph_workspace(args: argparse.Namespace) -> Path | None:
    """Workspace whose graph cache the command rewrites, if any."""
    if args.command in {"import", "sync"}:
        return args.workspace
    if args.command == "bootstrap":
        return args.workspace or _default_workspace()
    if args.command in {"maintain-graph", "restore-backup"}:
        return args.cache_dir.resolve().parent
    return None


def _run_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "import":
        result = import_suite(args.skill_root, args.suite_id, args.workspace,
                              exclude_skill_dirs=_labontology_dirs(args.skill_root.resolve()))
    elif args.command == "sync":
        if args.all and args.suite_id:
            raise ValueError("--all cannot be combined with --suite-id")
        # Like bootstrap, never register LabOntology itself as a Worker.
        excluded = _labontology_dirs(args.skill_root.resolve())
        result = (sync_workspace_all(args.skill_root, args.workspace, exclude_skill_dirs=excluded) if args.all
                  else sync_workspace(args.skill_root, args.workspace, args.suite_id, exclude_skill_dirs=excluded))
    elif args.command == "bootstrap":
        result = ensure_workspace_cache(args.workspace or _default_workspace(), args.skill_root or None)
    elif args.command == "resolve-cache":
        result = resolve_cache(args.skill_root, args.workspace, args.suite_id)
    elif args.command == "inspect":
        result = inspect_cache(args.cache_dir, args.skills)
    elif args.command == "run":
        result = run_mission(args.cache_dir, args.goal, args.mission_id, args.suite_id,
                             args.input_artifact, args.constraint, args.new_mission, args.plan,
                             args.run_through)
    elif args.command == "context":
        result = mission_context(args.cache_dir, args.mission_id, args.suite_id)
    elif args.command == "act":
        modes = [bool(args.decision_file), bool(args.skill), bool(args.ask), args.ask_plan, args.complete, args.cancel,
                 bool(args.revise)]
        if sum(modes) != 1:
            raise ValueError("act needs exactly one of: --decision-file, --skill, --ask, --ask-plan, --complete, "
                             "--cancel, --revise")
        if args.redo and not args.revise:
            raise ValueError("--redo belongs to --revise: act --revise \"<the user's change>\" --redo id1,id2")
        if args.input and not args.skill:
            raise ValueError("--input belongs to --skill: act --skill <Worker id> --input <artifact id>=<path>")
        if args.revise:
            result = revise_mission(args.cache_dir, args.mission_id, args.revise, args.redo, args.suite_id)
        elif args.decision_file:
            _reason_into_decision_file(args.decision_file, args.reason)
            result = act_mission(args.cache_dir, args.mission_id, args.decision_file, args.suite_id)
        else:
            result = act_shortcut(args.cache_dir, args.mission_id, args)
    elif args.command == "reconcile":
        result = reconcile_mission(args.cache_dir, args.mission_id, args.outcome, args.summary,
                                   suite_id=args.suite_id, evidence=args.evidence,
                                   provided_artifacts=args.provide_artifact)
    elif args.command == "prepare-skill":
        result = _prepare_fresh(args.cache_dir, args.mission_id, args.skill_id, args.suite_id)
    elif args.command == "restore-backup":
        result = restore_backup(args.cache_dir)
    elif args.command == "suggest-maintenance":
        result = suggest_maintenance(args.cache_dir, args.threshold, args.skill_id)
    elif args.command == "maintain-graph":
        result = maintain_graph(args.cache_dir, args.patch_file, args.reason)
    elif args.command == "resume":
        result = resume_mission(args.cache_dir, args.mission_id, suite_id=args.suite_id,
                                action_id=args.action_id, status=args.status,
                                confirm=args.confirm, reject=args.reject,
                                answer=args.answer, summary=args.summary, evidence=args.evidence,
                                provided_artifacts=args.provide_artifact,
                                agent_completed=args.agent_completed, agent_failed=args.agent_failed,
                                register_all=args.register_all)
    elif args.command == "status":
        # The raw state is ~15 KB; the digest has what is needed to continue (`context --full` for debugging).
        result = _context_digest(mission_context(args.cache_dir, args.mission_id), args)
        result["note"] = "Mission status (digest). Do what `do_next` says."
    elif args.command == "describe-skill":
        result = describe_skill(args.cache_dir, args.skill_id, args.suite_id)
    else:
        result = list_missions(args.cache_dir, args.query)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Release-facing LabOntology workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)
    import_parser = subparsers.add_parser("import", help="Create and validate a compact cache")
    import_parser.add_argument("skill_root", type=Path)
    import_parser.add_argument("--suite-id", required=True)
    import_parser.add_argument("--workspace", type=Path, default=Path.cwd())
    sync_parser = subparsers.add_parser("sync", help="Synchronize a Skill root into the workspace cache")
    sync_parser.add_argument("--skill-root", type=Path, required=True)
    sync_parser.add_argument("--workspace", type=Path, default=Path.cwd())
    sync_parser.add_argument("--suite-id")
    sync_parser.add_argument("--all", action="store_true")
    bootstrap_parser = subparsers.add_parser("bootstrap", help="Create or reuse the workspace cache")
    bootstrap_parser.add_argument("--workspace", type=Path, default=None)
    bootstrap_parser.add_argument("--skill-root", action="append", type=Path, default=[])
    # The other commands take --cache-dir and agents copy it onto bootstrap; accept it instead of failing.
    bootstrap_parser.add_argument("--cache-dir", type=Path, default=None, help=argparse.SUPPRESS)
    resolve_parser = subparsers.add_parser("resolve-cache", help="Find a valid existing cache for a Skill directory")
    resolve_parser.add_argument("--skill-root", type=Path, required=True)
    resolve_parser.add_argument("--workspace", type=Path, default=Path.cwd())
    resolve_parser.add_argument("--suite-id")
    inspect_parser = subparsers.add_parser("inspect", help="Summarize a compact cache")
    inspect_parser.add_argument("--cache-dir", type=Path, required=True)
    inspect_parser.add_argument("--skills", action="store_true",
                                help="Also list each Worker's id, name and short description")
    run_parser = subparsers.add_parser("run", help="Create an Agent-mode mission")
    run_parser.add_argument("--cache-dir", type=Path, required=True)
    run_parser.add_argument("--goal", required=True)
    run_parser.add_argument("--mission-id")
    run_parser.add_argument("--suite-id")
    run_parser.add_argument("--input-artifact", action="append", default=[], metavar="ARTIFACT_ID=PATH")
    run_parser.add_argument("--constraint", action="append", default=[])
    run_parser.add_argument("--plan", default="",
                            help="Comma-separated Worker ids in the order the goal needs them (multi-step requests)")
    run_parser.add_argument("--run-through", action="store_true",
                            help="Only when the user asked for all steps at once: no pause for the user after each plan step")
    run_parser.add_argument("--new-mission", action="store_true",
                            help="Create a new mission even though another one is waiting for the user's answer")
    context_parser = subparsers.add_parser("context", help="Return the current task context")
    context_parser.add_argument("--cache-dir", type=Path, required=True)
    context_parser.add_argument("--mission-id", required=True)
    context_parser.add_argument("--suite-id")
    context_parser.add_argument("--full", action="store_true", help="Uncompacted output (debugging)")
    act_parser = subparsers.add_parser("act", help="Issue one action decision for the current task")
    act_parser.add_argument("--cache-dir", type=Path, required=True)
    act_parser.add_argument("--mission-id", required=True)
    act_parser.add_argument("--decision-file", type=Path)
    act_parser.add_argument("--skill", help="Run this Worker next (the Runtime writes the decision for you)")
    act_parser.add_argument("--retry-of", help="Failed action id when re-running the same Worker")
    act_parser.add_argument("--input", action="append", default=[], metavar="ARTIFACT_ID=PATH",
                            help="With --skill: an input file for the Worker that the mission does not hold yet "
                                 "(for example artifact:parsed-constraints=<uploaded file>); repeatable")
    act_parser.add_argument("--ask", help="Ask the user one question and wait for the answer")
    act_parser.add_argument("--ask-plan", action="store_true", help="Ask the user to confirm the mission's --plan")
    act_parser.add_argument("--complete", action="store_true", help="Close the mission once all results are recorded")
    act_parser.add_argument("--cancel", action="store_true",
                            help="Close the mission because the user stopped it; during a revision, drop only that change")
    act_parser.add_argument("--revise", default="",
                            help="The user's change to a finished task: reopen this mission and redo only --redo Workers")
    act_parser.add_argument("--redo", default="", help="Comma-separated Worker ids to run again (with --revise)")
    act_parser.add_argument("--reason", default="")
    act_parser.add_argument("--suite-id")
    reconcile_parser = subparsers.add_parser("reconcile", help="Reconcile an interrupted action")
    reconcile_parser.add_argument("--cache-dir", type=Path, required=True)
    reconcile_parser.add_argument("--mission-id", required=True)
    reconcile_parser.add_argument("--suite-id")
    reconcile_parser.add_argument("--outcome", choices=("not_started", "succeeded", "failed", "unknown"), required=True)
    reconcile_parser.add_argument("--summary", required=True)
    reconcile_parser.add_argument("--evidence", action="append", default=[])
    reconcile_parser.add_argument("--provide-artifact", action="append", default=[], metavar="ARTIFACT_ID=PATH")
    prepare_parser = subparsers.add_parser("prepare-skill", help="Read a Worker Skill before issuing an action")
    prepare_parser.add_argument("--cache-dir", type=Path, required=True)
    prepare_parser.add_argument("--mission-id", required=True)
    prepare_parser.add_argument("--skill-id", required=True)
    prepare_parser.add_argument("--suite-id")
    restore_parser = subparsers.add_parser("restore-backup", help="Restore the latest graph backup")
    restore_parser.add_argument("--cache-dir", type=Path, required=True)
    suggest_parser = subparsers.add_parser("suggest-maintenance", help="Suggest read-only graph maintenance targets")
    suggest_parser.add_argument("--cache-dir", type=Path, required=True)
    suggest_parser.add_argument("--threshold", type=int, default=3)
    suggest_parser.add_argument("--skill-id")
    maintain_parser = subparsers.add_parser("maintain-graph", help="Apply a validated low-risk graph patch")
    maintain_parser.add_argument("--cache-dir", type=Path, required=True)
    maintain_parser.add_argument("--patch-file", type=Path, required=True)
    maintain_parser.add_argument("--reason", required=True)
    resume_parser = subparsers.add_parser("resume", help="Resume an Agent-mode mission")
    resume_parser.add_argument("--cache-dir", type=Path, required=True)
    resume_parser.add_argument("--mission-id", required=True)
    resume_parser.add_argument("--suite-id")
    resume_parser.add_argument("--action-id", default="", help="External Skill action being reported")
    resume_parser.add_argument("--status", choices=("succeeded", "failed"),
                               help="External Skill result when --action-id is supplied")
    resume_parser.add_argument("--confirm", action="store_true")
    resume_parser.add_argument("--reject", action="store_true")
    resume_parser.add_argument("--answer", default="")
    resume_parser.add_argument("--summary", default="")
    resume_parser.add_argument("--evidence", action="append", default=[])
    resume_parser.add_argument("--provide-artifact", action="append", default=[], metavar="ARTIFACT_ID=PATH")
    resume_parser.add_argument("--agent-completed", action="store_true")
    resume_parser.add_argument("--agent-failed", action="store_true")
    resume_parser.add_argument("--register-all", action="store_true",
                               help="Register every unregistered file in the mission artifact folder")
    status_parser = subparsers.add_parser("status", help="Show a persisted mission")
    status_parser.add_argument("--cache-dir", type=Path, required=True)
    status_parser.add_argument("--mission-id", required=True)
    describe_parser = subparsers.add_parser("describe-skill", help="Read full details for one selected Skill")
    describe_parser.add_argument("--cache-dir", type=Path, required=True)
    describe_parser.add_argument("--skill-id", required=True)
    describe_parser.add_argument("--suite-id")
    missions_parser = subparsers.add_parser("missions", help="List persisted Agent missions")
    missions_parser.add_argument("--cache-dir", type=Path, required=True)
    missions_parser.add_argument("--query")
    args = parser.parse_args(argv)
    blocked = _repeat_guard(args)
    if blocked is not None:
        print(_render(blocked, False))
        return 0 if blocked.get("bootstrap_skipped") else 3  # a skipped bootstrap must not break `bootstrap; context` chains
    try:
        workspace = _graph_workspace(args)
        # One graph writer per workspace; mission commands lock their own mission.
        lock = (file_lock(Path(workspace).resolve() / ".labontology_workspace_cache.lock")
                if workspace is not None else contextlib.nullcontext())
        with lock:
            result = _run_command(args)
        if args.command == "context" and _LAST_REPEAT_COUNT >= _DIGEST_FROM:
            result = _context_digest(result, args)
        elif args.command in _MISSION_COMMANDS and not getattr(args, "full", False):
            result = _compact_result(result)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"labontology.py {args.command}: {_user_facing_error(exc)}", file=sys.stderr)
        return 2
    except Exception as exc:
        # The caller is an experiment-facing Agent: report, never dump a traceback.
        if os.environ.get("LABONTOLOGY_DEBUG"):
            raise
        parser.error(f"LabOntology 遇到未预期的问题（{type(exc).__name__}）：{exc}")
    print(_render(result, args.command in _MISSION_COMMANDS and not getattr(args, "full", False)))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
