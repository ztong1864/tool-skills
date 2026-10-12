from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = SKILL_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"druglikeness_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
            "scripts/rdkit_assess.py",
            "scripts/verify_output.py",
            "assets/test_molecules.csv",
            "assets/expected_output.csv",
            "HANDOFF.md",
        )
        for relative in required:
            self.assertTrue((SKILL_ROOT / relative).is_file(), relative)

    def test_frontmatter_name_matches_directory(self):
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        self.assertIn("name: druglikeness-assessment", text)

    def test_openai_prompt_names_skill(self):
        text = (SKILL_ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
        self.assertIn("$druglikeness-assessment", text)


class WrapperContractTests(unittest.TestCase):
    def test_blank_smiles_is_invalid(self):
        module = load_script("rdkit_assess")
        self.assertTrue(module.is_blank_smiles("  "))
        self.assertTrue(module.is_blank_smiles(None))
        self.assertFalse(module.is_blank_smiles("CC"))

    def test_read_input_preserves_order_and_duplicate_ids(self):
        module = load_script("rdkit_assess")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.csv"
            write_csv(
                path,
                ["compound_id", "smiles", "ignored"],
                [
                    {"compound_id": "x", "smiles": "CC", "ignored": "1"},
                    {"compound_id": "x", "smiles": "CCC", "ignored": "2"},
                ],
            )
            rows = module.read_input(path, "compound_id", "smiles")
        self.assertEqual([row["compound_id"] for row in rows], ["x", "x"])
        self.assertEqual([row["smiles"] for row in rows], ["CC", "CCC"])

    def test_missing_smiles_column_raises(self):
        module = load_script("rdkit_assess")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.csv"
            write_csv(path, ["compound_id", "structure"], [{"compound_id": "x", "structure": "CC"}])
            with self.assertRaisesRegex(ValueError, "SMILES column"):
                module.read_input(path, "compound_id", "smiles")


class FixtureAndVerifierTests(unittest.TestCase):
    def test_expected_output_shape_and_unique_header(self):
        path = SKILL_ROOT / "assets/expected_output.csv"
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(len(rows) - 1, 20)
        self.assertEqual(len(rows[0]), 13)
        self.assertEqual(len(set(rows[0])), 13)

    def test_verifier_rejects_changed_lipinski_flag(self):
        verifier = load_script("verify_output")
        expected = SKILL_ROOT / "assets/expected_output.csv"
        with expected.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        rows[0]["Lipinski"] = "0" if rows[0]["Lipinski"] == "1" else "1"
        with tempfile.TemporaryDirectory() as tmp:
            actual = Path(tmp) / "actual.csv"
            write_csv(actual, fieldnames, rows)
            errors, _summary = verifier.compare_csv(actual, expected, 1e-6)
        self.assertTrue(any("Lipinski" in error for error in errors))

    def test_verifier_rejects_nonfinite_numeric_value(self):
        verifier = load_script("verify_output")
        expected = SKILL_ROOT / "assets/expected_output.csv"
        with expected.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        rows[0]["QED"] = "nan"
        with tempfile.TemporaryDirectory() as tmp:
            actual = Path(tmp) / "actual.csv"
            write_csv(actual, fieldnames, rows)
            errors, _summary = verifier.compare_csv(actual, expected, 1e-6)
        self.assertTrue(any("nonfinite" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
