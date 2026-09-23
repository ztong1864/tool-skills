TRIAGE_SYSTEM = (
    "You are a chemistry extraction triage agent. "
    "Classify whether the input is useful for reaction condition optimization. "
    "Be strict and choose exactly one doc_type from the allowed list."
)

TRIAGE_USER_TEMPLATE = """\
You are given text extracted from a single PDF page.
Return a JSON object with:
- doc_type: one of [OPTIMIZATION_TABLE, SCOPE, PROCEDURE, MECHANISM, SPECTRA, OTHER, UNKNOWN]
- usefulness_score: 0-1 float
- keep: boolean (true if should proceed to extraction)
- keep_reason: short string
- drop_reason: short string (empty if keep=true)
- suspected_system_tag: boolean (true if likely describes an ATA/EATA asymmetric alkynylation/allenylation page)

Important rules:
- If doc_type is MECHANISM or SPECTRA, set keep=false.
- Prefer OPTIMIZATION_TABLE when tabulated conditions/yields are visible.
- Set keep=true for pages describing ATA/EATA asymmetric alkynylation/allenylation reactions,
  even if the exact catalysts, ligands, solvents, or additives are outside the current allowed values.
- Set keep=false and suspected_system_tag=false for non-ATA/EATA chemistry, including aerobic oxidation,
  hydrolysis, protection/deprotection, reduction, substrate preparation, and workup-only procedures.
- Allowed values below are only downstream BO-space hints, not page-level exclusion criteria.

Target scope:
{target_scope}

Provenance:
{provenance}

Page text:
{page_text}
"""


def _json_field_lines(reaction_columns, value_type: str, indent: str = "    ") -> str:
    return "\n".join(f'{indent}"{col}": null or {value_type}' for col in reaction_columns)


def _json_evidence_lines(reaction_columns, indent: str = "    ") -> str:
    return "\n".join(f'{indent}"{col}": "..."' for col in reaction_columns)


def build_fact_user_prompt(reaction_columns, *, source_id: str, doc_type: str, default_conditions: str, page_text: str, candidate: str):
    field_lines = _json_field_lines(reaction_columns, "string")
    evidence_lines = _json_evidence_lines(reaction_columns)
    return f"""\
Return a JSON object with these keys:
{{
  "record": {{
    "source_id": "...",
    "record_id": "...",
    "paper_id": "...",
    "doc_type": "...",
{field_lines},
    "yield_percent": null or number,
    "notes": string
  }},
  "evidence": {{
{evidence_lines},
    "yield_percent": "..."
  }},
  "missing_fields": [...],
  "confidence": 0-1
}}
If a field cannot be determined, set it to null and explain in missing_fields.
Use the provided default_conditions if available.
Use canonical short labels when possible, such as CuI, CuBr, AgOTf, AuSIPrNTf2, dp_prolinol, silyl_dp_prolinol, binaphthyl_prolinol, DCE, TFE, toluene, MeCN, Dioxane, 4A MS 20.00 mg, none.

Source:
{source_id}

Page text:
{page_text}

Doc type:
{doc_type}

Default conditions (if any):
{default_conditions}

Candidate:
{candidate}
"""


CANDIDATE_SYSTEM = (
    "You are a chemical reaction candidate extractor. "
    "Extract reaction entries from extracted PDF text."
)

CANDIDATE_USER_TEMPLATE = """\
From the page text, produce a JSON object:
{{
  "candidates": [
    {{
      "reaction_id": "...",
      "reaction_key_guess": "...",
      "reactant_smiles": [...],
      "product_smiles": [...],
      "conditions_texts": [...],
      "additional_info_texts": [...]
    }}
  ]
}}
Use empty lists if missing. Do not invent data.
Extract only target ATA/EATA asymmetric alkynylation/allenylation candidates
from pages that match the target reaction family. Do not require catalysts,
ligands, solvents, or additives to be in the current allowed values at this
candidate stage. Do not extract aerobic oxidation, hydrolysis,
protection/deprotection, reduction, substrate preparation, or workup-only steps.

Target scope:
{target_scope}

Page text:
{page_text}
"""


FACT_SYSTEM = (
    "You are a chemistry information extraction agent. "
    "Map a single candidate reaction to a structured FactRecord. "
    "Use nullable fields if uncertain; do not guess."
)

DEFAULT_SYSTEM = (
    "You are a chemistry procedure summarizer. "
    "Derive default conditions for a paper or table from multiple records."
)

def build_default_user_prompt(reaction_columns, *, records):
    field_lines = _json_field_lines(reaction_columns, "string", indent="      ")
    return f"""\
Given these records, infer one or more default condition sets.
Return JSON:
{{
  "defaults": [
    {{
      "default_id": "...",
{field_lines},
      "notes": "..."
    }}
  ]
}}
If you cannot infer defaults, return an empty list.

Records:
{records}
"""


MERGE_SYSTEM = (
    "You are a data curator. "
    "Identify duplicate experiments among structured records."
)

MERGE_USER_TEMPLATE = """\
Return JSON:
{{
  "merge_groups": [
    {{
      "record_ids": ["...","..."],
      "representative_id": "..."
    }}
  ]
}}
Only merge if you are confident they represent the same experimental conditions.

Records:
{records}
"""


NORMALIZE_SYSTEM = (
    "You are a chemistry data normalization agent. "
    "Normalize and standardize reaction condition fields based on evidence and context. "
    "Be conservative and do not invent values."
)

def build_normalize_user_prompt(reaction_columns, *, paper_context, record):
    field_lines = _json_field_lines(reaction_columns, "string", indent="    ")
    return f"""\
Return JSON with a single key:
{{
  "normalized": {{
{field_lines},
    "yield_percent": null or number
  }},
  "notes": "short explanation of key normalization choices"
}}

Normalization requirements:
- Use evidence and context only. If uncertain, return null.
- Keep canonical formats:
  - reaction columns: prefer canonical short labels from the project temp header and descriptor tables.
  - solvent: prefer common abbreviations (DCE, DCM, DMF, THF, CH3CN, TFE, toluene, Dioxane, MeCN).
- Yield priority: if both NMR and isolated yields appear, prefer isolated.

Hard constraints (MUST follow):
- Optional absence columns may be null or "none" when absent.
- solvent MUST contain solvent only; do not include quench or workup solvents.
- If you cannot confidently normalize a field into the canonical format, return null for that field.

Paper context (defaults and common values):
{paper_context}

Record evidence:
{record}
"""
