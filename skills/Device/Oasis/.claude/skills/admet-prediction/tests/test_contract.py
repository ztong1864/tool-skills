from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = SKILL_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"admet_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class SkillStructureTests(unittest.TestCase):
    def test_required_files_exist(self):
        required = (
            "SKILL.md",
            "agents/openai.yaml",
            "scripts/admet_predict.py",
            "scripts/verify_output.py",
            "scripts/install_offline.sh",
            "environment-base.yml",
            "requirements-lock.txt",
            "wheels_sha256.txt",
            "assets/test_molecules.csv",
            "assets/expected_output.csv",
            "HANDOFF.md",
        )
        for relative in required:
            self.assertTrue((SKILL_ROOT / relative).is_file(), relative)

    def test_frontmatter_and_prompt_match_skill(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        ui = (SKILL_ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
        self.assertIn("name: admet-prediction", skill)
        self.assertIn("$admet-prediction", ui)


class WrapperContractTests(unittest.TestCase):
    def test_blank_smiles_is_invalid(self):
        module = load_script("admet_predict")
        self.assertTrue(module.is_blank_smiles("\t"))
        self.assertTrue(module.is_blank_smiles(None))
        self.assertFalse(module.is_blank_smiles("CC"))

    def test_assembly_preserves_order_and_marks_invalid(self):
        module = load_script("admet_predict")
        rows = [
            {"compound_id": "a", "smiles": "CC"},
            {"compound_id": "b", "smiles": "bad"},
        ]
        result = module.assemble_output(rows, [0], [{"AMES": 0.2}], ["AMES"])
        self.assertEqual(result[0]["status"], "OK")
        self.assertEqual(
            result[1],
            {"smiles": "bad", "compound_id": "b", "status": "INVALID_SMILES", "AMES": ""},
        )

    def test_assembly_rejects_wrong_prediction_count(self):
        module = load_script("admet_predict")
        rows = [{"compound_id": "a", "smiles": "CC"}]
        with self.assertRaisesRegex(ValueError, "prediction row count"):
            module.assemble_output(rows, [0], [], ["AMES"])


class FixtureAndPortabilityTests(unittest.TestCase):
    def test_expected_output_has_101_unique_columns(self):
        header, _rows = read_csv(SKILL_ROOT / "assets/expected_output.csv")
        self.assertEqual(len(header), 101)
        self.assertEqual(len(set(header)), 101)
        self.assertEqual(header[:3], ["smiles", "compound_id", "status"])

    def test_invalid_row_has_status_and_empty_results(self):
        header, rows = read_csv(SKILL_ROOT / "assets/expected_output.csv")
        row = rows[-1]
        self.assertEqual(row["status"], "INVALID_SMILES")
        self.assertTrue(all(row[name] == "" for name in header[3:]))

    def test_portable_files_have_no_server_paths(self):
        portable = (
            "environment-base.yml",
            "requirements-lock.txt",
            "wheels_sha256.txt",
            "scripts/install_offline.sh",
            "scripts/admet_predict.py",
        )
        for relative in portable:
            text = (SKILL_ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("/slurm/", text, relative)
            self.assertNotIn("file:///home/", text, relative)
            self.assertNotIn("prefix:", text, relative)

    def test_hash_manifest_uses_basenames(self):
        lines = (SKILL_ROOT / "wheels_sha256.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 68)
        for line in lines:
            digest, filename = line.split(maxsplit=1)
            self.assertEqual(len(digest), 64)
            self.assertNotIn("/", filename)

    def test_verifier_rejects_nonfinite_valid_prediction(self):
        verifier = load_script("verify_output")
        expected = SKILL_ROOT / "assets/expected_output.csv"
        header, rows = read_csv(expected)
        rows[0]["AMES"] = "nan"
        with tempfile.TemporaryDirectory() as tmp:
            actual = Path(tmp) / "actual.csv"
            write_csv(actual, header, rows)
            errors, _summary = verifier.compare_csv(actual, expected, 1e-4)
        self.assertTrue(any("nonfinite" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
