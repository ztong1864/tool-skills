# Examples

`run_43789.sh` runs a serum sickness (`disease_id=43789`) top-100 scoring job and writes `score_43789_top100.csv`.

The online Oasis skill uses the existing Python venv at `/home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/primekg`. DGL is required by inference but is currently absent from that venv, so a real score CSV can only be generated after DGL is installed and the verifier passes. Do not switch to a Conda environment for this deployment.

`output_schema.csv` contains only the expected header and no model scores. Do not treat it as a prediction result.
