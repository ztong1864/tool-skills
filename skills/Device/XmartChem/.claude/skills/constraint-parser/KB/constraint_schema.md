# Constraint Parser JSON Schema

The parser output must be one JSON object with these top-level fields:

- `schema_version`: string, currently `"constraint-parser/simple-v1"`.
- `created_at`: string timestamp in local time.
- `items`: array of component objects.
- `ambiguities`: array of strings.
- `source_text`: original user instruction string.

## item object

Required fields:

- `name`: exact name or category phrase from the user text. Examples: `"金属盐"`, `"苯乙炔"`.
- `group`: `"reagent"`, `"substrate"`, `"solvent"`, or `"condition"`.
- `equivalent`: number or null. Use only 当量/equiv values.
- `quantity`: object or null. Use only mass or volume values.
- `physical_state`: `"solid"`, `"liquid"`, or null.
- `raw_text`: the original phrase for this item.

Optional field:

- `note`: short string or null. Use it only for simple details such as `"1种或2种"` or `"不加入或20 mg"`.

## General Rules

- Preserve exact user-facing chemical names.
- Do not hallucinate candidate chemical identities.
- Do not build optimization domains, device steps, or nested condition structures.
- Do not extract non-equivalent quantities into `equivalent`. For example, `0.1 mmol`, `20 mg`, and `1 mL` are not equivalents.
- Extract mass or volume into `quantity` as `{ "value": number, "unit": string }`. Examples: `20 mg`, `1 mL`.
- If no mass or volume appears for an item, set `quantity` to null.
- Do not put substance amount such as `0.1 mmol` into `quantity`; keep it in `note` if useful.
- Put simple non-equivalent information in `note` only when it matters.
- Put missing or ambiguous details in `ambiguities`.
- Use null for unknown values.
- Output valid JSON only.
