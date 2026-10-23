# Repository audit: structure, redundancy and leftover files

Audit of every skill (`SKILL.md`) and tool (`TOOL.md`) in this repository, made on 2026-10-23 at commit
`1faad7c`. Nothing was changed or deleted. This file only records the findings and the decisions that are still
open.

## 1. Current layout

```
skills/
  Device/
    .agents/skills/              12 skills: a third copy of iBioFoundry, belongs to no device
    iBioFoundry/
      .agents/skills/            12 skills
      .claude/skills/            the same 12 skills, byte-identical
    iChemFoundry/
      .claude/skills/            3 skills
      memory/, research-wiki/    device data read by mof-recommendation
      README.md, recomm_steps.md, task_plan.md, findings.md, progress.md
    Oasis/.claude/skills/        22 skills
    XmartChem/.claude/skills/    20 skills
    XtalPi/.claude/skills/       19 skills (16 share names with XmartChem)
  Public/general/.claude/skills/ 30 skills + 2 shared code libraries (_review_runtime, review_writer_core)
tools/
  Device/<6 devices>/.claude/tools/   only XmartChem has a tool (trace-collab); the other 5 hold only .gitkeep
  Plugin/.claude/tools/               20 tools: external MCP services and ToolUniverse bundles
  Public/chemistry/.claude/tools/     1 tool (element-info)
  tool-service/                       shared ToolUniverse bridge + vendored ToolUniverse package
```

## 2. Recommended layout

1. **One copy of each skill per device, in `.claude/skills/`.** The iBioFoundry skill documents only refer to
   `.claude/skills/...` paths. LabOntology (`labontology/scripts/labontology.py`, `discover_skill_roots`)
   searches `.agents/skills`, `.agent/skills`, `.claude/skills`, `.codex/skills` and `skills/`, so a device that
   ships both `.agents` and `.claude` copies lists every skill twice when both are present.
2. **A device folder holds that device's skills, plus device data only when a skill reads it** (for example
   `iChemFoundry/memory/`, read by `mof-recommendation`). Nothing sits directly under `skills/Device/`.
3. **A skill's folder name matches the `name:` in its `SKILL.md`**, and `SKILL.md` is its only instruction file.
4. **Code shared by several skills lives outside the skills folder** (or in a clearly named library folder), not
   mixed in with the skills.
5. **Run results are never committed.** A run writes into its task's own output folder. Today `.gitignore` only
   covers `skills/Device/XmartChem/.claude/skills/*/output/`.
6. **Tools:** `tools/Device/<device>/` for device-specific tools, `tools/Plugin/` for external services and
   ToolUniverse bundles, `tools/Public/<category>/` for general local tools. The header docstring of
   `tools/tool-service/tooluniverse_bridge.py` still says local ToolUniverse tools go in `tools/Public/`, but they
   actually live in `tools/Plugin/.claude/tools/tooluniverse-*-tools`.

## 3. Redundant or overlapping skills and tools

| What | Verdict |
|---|---|
| `skills/Device/.agents/skills/` and `skills/Device/iBioFoundry/.agents/skills/` | **Redundant.** Both are byte-identical to `skills/Device/iBioFoundry/.claude/skills/`; recent commits edit all three copies by hand. |
| XtalPi: the 16 skills it shares with XmartChem | **Out-of-date copy.** Both target the same Fudan workstation API (`FDU_DEVICE_BASE_URL`). `fdu-filter-json`, `fdu-multi-step-json` and `fdu-suzuki-device-json` are byte-identical; the others mostly lack later XmartChem fixes (for example the `.env` path handling). XtalPi's `fdu-add-liquid-json/SKILL.md` says it outputs `exp_add_liquid`, but its script emits `exp_pipetting`, the same as XmartChem. |
| XtalPi: `experiment-skills-ctrl` | Appears superseded by XmartChem's `fdu-ontology` together with LabOntology's experiment flows (`experiment_flows.yaml`). |
| XtalPi: `bo-optimizer`, `chem-info-extractor` | Unique; keep. |
| Oasis: `primekg-drug-recommendation` vs `primekg-cgi-drug-effect-prediction` | **Overlapping.** Both turn a disease ID or name into a ranked drug CSV from PrimeKG, using different models. Only `primekg-drug-recommendation` says it is the preferred one. Merge them, or state in both descriptions when to use each. |
| Public: `review-literature-acquisition` vs `review-online-paper-discovery` | **Partly overlapping.** Both go topic → Crossref → PDF → shared paper library; acquisition downloads open-access PDFs automatically, discovery relies on manual downloads. `sciatlas_client.py` exists three times: identical copies in both discovery skills' `scripts/`, and a variant in `review_writer_core/`. |
| Oasis `oasis-ontology` vs XmartChem `fdu-ontology` | Each carries its own copy of the same graph library (`oasis_graph/` vs `fdu_graph/`): `entities.py` and `utils.py` are identical, `store.py` and `relations.py` are 91–98% the same. Could become one shared library. |
| Public: `review-cross-study-synthesis` | No other skill or script refers to it by name. |
| Public: `summarize` | Needs an external `summarize` command-line program (installed via Homebrew), which is probably not on the server. |
| Plugin `tooluniverse-chemistry-tools` vs Oasis `druglikeness-assessment` | Overlap on Lipinski, QED and PAINS. Acceptable: the Oasis skill ships its own tested environment. |
| Plugin `scitoolagent-chem` vs `scp-chem-reaction-calc` | Two external chemistry services with overlapping catalogues (169 and 105 sub-tools). Expected for remote services; keep both if both are reachable. |
| `trace-collab` tool + `trace-collab-skill` | **Not redundant.** The tool makes the calls; the skill tells the agent how to drive it. The wording is stale: `TOOL.md` says it "replaces" the skill, and the skill's description starts "Use when Codex needs to…". |
| `imagej-analyzer` + `hci-image-analysis` | **Not redundant.** `hci-image-analysis` explicitly hands single images, Western blots and colocalization to `imagej-analyzer`. |
| `fdu-filter-json` + `fdu-high-filter-json` | **Not redundant.** Separate device actions (`exp_filtering_samples` vs `exp_high_filtering_samples`). |

## 4. Leftover and redundant files

### 4.1 Clearly rubbish (673 files)

**XtalPi test-run outputs: 663 files, about 4.4 MB.** Everything tracked under
`skills/Device/XtalPi/.claude/skills/*/output/` except `bo-optimizer/output/opt_round_*`. These are results of
development runs from April 2026, the same kind of files already removed from XmartChem in commit `265d4dc`.

| Skill | Files | Content |
|---|---:|---|
| `chem-info-extractor/output/` | 418 | 409 page-text files from PDFs named `s (1)`–`s (5)` (many pages repeated across `s (2)`/`s (3)`/`s (4)`), a saved log of AI-model calls (`logs/llm_cache.jsonl`), one run folder |
| `fdu-add-liquid-json/output/` | 60 | `generated_add_liquid_<timestamp>.json` |
| `fdu-reaction-control-json/output/` | 49 | `generated_reaction_control_<timestamp>.json` |
| `fdu-add-solid-json/output/` | 33 | `generated_add_solid_<timestamp>.json` |
| `fdu-experiment-plan/output/` | 30 | 3 run folders × 10 plans |
| `fdu-step-json/output/` | 22 | `generated_step_json_<timestamp>.json` |
| `fdu-high-filter-json/output/` | 13 | several byte-identical to each other |
| `constraint-parser/output/` | 9 | `parsed_constraints_*.json` |
| `chemical-amount-calculator/output/` | 7 | `chemical_amount_*.csv` |
| `fdu-unit-orchestration-json/output/` | 6 | includes `test_generated_protocol.json` |
| `experiment-step-generator/output/` | 5 | 3 of them identical |
| `fdu-resource-verify/output/` | 5 | verification results |
| `fdu-multi-step-json/output/` | 4 | |
| `bo-optimizer/output/ata_top10_recommendations_20260427.csv` | 1 | |
| `fdu-device-run/output/ata_task_confirmation.txt` | 1 | |

**Other clear rubbish (10 files):**

- `skills/Device/iChemFoundry/memory/knowledge_base/v3.4/build_progress_v3.json.bak2`: an older backup; the
  current `build_progress_v3.json` contains everything in it and more.
- `skills/Device/iChemFoundry/memory/knowledge_base/v4/material/v3.4.lnk`: a Windows shortcut to
  `D:\Work\ZJU_project\...` on one PC; it does not work anywhere else.
- `skills/Device/iChemFoundry/memory/knowledge_base/v4/bridge_indexes/lever_to_candidate_filter.json`: an exact
  copy of the same file in `v4/bridge/`.
- `skills/Device/XmartChem/.claude/skills/fdu-resource-verify/KB/resource_info_20260413_174715.json` and
  `resource_info_20260703_105427.json`: superseded snapshots. `verify_resources.py` only reads the newest one, and
  `_105427` equals `_105739` apart from its timestamp.
- `skills/Device/Oasis/.claude/skills/primekg-drug-recommendation/src/disease_15667_scores.csv`: a stray scoring
  result for one disease (6,945 rows) left in `src/`; nothing refers to it.
- `fdu-reaction-control-json/scripts/fetch_resource_info.py` in both XmartChem and XtalPi: nothing calls it. It is
  an older copy of `fdu-resource-verify/scripts/fetch_resource_info.py` and falls back to a built-in device IP and
  `admin`/`admin` login.
- `fdu-suzuki-device-json/KB/resource_info-1.json` in both XmartChem and XtalPi: nothing refers to it; the code
  only reads `KB/resource_info.json`.

### 4.2 Borderline: owner's decision (110 files)

- `skills/Device/.agents/skills/` (105 files): see section 3.
- `skills/Device/iChemFoundry/task_plan.md`, `findings.md`, `progress.md`: notes from one planning-with-files
  session in June 2026 that stopped at "Phase 3 in progress". `mof-recommendation/SKILL.md` deliberately marks
  them as records of the original project that must not be read or modified.
- `skills/Device/Oasis/.claude/skills/primekg-cgi-drug-effect-prediction/server_claude_code_graph_cgi_e50_smoke_test_handoff.md`
  and `server_codex_mce_primekg_initial_scoring_handoff.md`: instructions for two one-off server tasks; nothing
  refers to them.

### 4.3 References to update if those files are removed

- `skills/Device/XtalPi/.claude/skills/literature-experiment-recommender/KB/input_sources.md` points at
  `constraint-parser/output/parsed_constraints_2026-04-27-13-31-19.json` and
  `bo-optimizer/output/ata_top10_recommendations_20260427.csv`. XmartChem's copy was already rewritten to point
  at the task's own files and `KB/output_format_example.csv`.
- `experiment-step-generator/scripts/generate_steps.py` (`DEFAULT_CONSTRAINTS`, in both XtalPi and XmartChem)
  defaults to the same `parsed_constraints_2026-04-27-13-31-19.json`. In XmartChem that file is already gone, so
  running the script without `--constraints` fails there today.
- `skills/Device/iChemFoundry/.claude/skills/mof-recommendation/SKILL.md` lines 22, 26 and 88 tell the agent to
  search `v4/material/`, but that folder holds only the `.lnk` shortcut. The material data is in
  `v3.4/structured/`, so this is already broken now.
- The same `SKILL.md`, line 16, mentions `task_plan.md`, `findings.md` and `progress.md`.
- `memory/knowledge_base/v4/principle/KB_V4_完成报告.md` line 232 lists `bridge_indexes/`; that section of the report
  is already out of date.

### 4.4 Checked and kept

- `skills/Device/XtalPi/.claude/skills/bo-optimizer/output/opt_round_*` (7 files): real experiment yields from
  2025, not copied anywhere else.
- `KB/temp.json` and `KB/temp_step.json`: read by the scripts.
- `tools/tool-service/vendor/tooluniverse/`: an upstream copy loaded by the bridge; its empty files come from
  upstream.
- `tools/Device/*/.claude/tools/.gitkeep`: keep otherwise-empty tool folders in git.
- The repeated office scripts in `docx/`, `pptx/` and `xlsx/`: the upstream layout, where each skill is
  self-contained.

## 5. Structural inconsistencies

- `skills/Device/iChemFoundry/.claude/skills/IC-solvent-condition-generator` and `IC-solvent-experiment-plan` are
  named `mof-condition-generator` and `mof-task-planner` in their `SKILL.md`, and each also has a separate
  `prompt.md` with instructions.
- `skills/Public/general/.claude/skills/_review_runtime/` and `review_writer_core/` are code libraries (no
  `SKILL.md`) inside the skills folder; 21 review scripts import them.
- `tools/Device/` has empty placeholder folders for JAKA, Oasis, XtalPi, iBioFoundry and iChemFoundry. JAKA has
  no skills folder at all.
- `.gitignore` ignores run outputs only for XmartChem, not for XtalPi or the other devices.

## 6. Security

The 12 Oasis API skills (`skills/Device/Oasis/.claude/skills/oasis-*/scripts/call.py`, all except
`oasis-ontology`) contain a plain-text SSH host, username and password in the source. The FDU skills read their
credentials from environment variables (`FDU_DEVICE_*`) instead. The Oasis values should move to environment
variables as well, and the password should be changed on the server, because it remains in git history even
after it is removed from the files.

## 7. Open decisions

1. **Is XtalPi a separate physical device?** If not, move `bo-optimizer` and `chem-info-extractor` into
   XmartChem (or Public) and remove the rest of the XtalPi skills. If it is, its 16 shared skills need to be
   brought up to date with XmartChem.
2. **Is either `.agents/skills` copy used by a Codex setup?** If not, both can be removed, keeping only
   `skills/Device/iBioFoundry/.claude/skills/`.
3. **PrimeKG skills:** merge `primekg-drug-recommendation` and `primekg-cgi-drug-effect-prediction`, or write in
   both descriptions when each should be used.
4. **Borderline files in 4.2:** keep or remove.
