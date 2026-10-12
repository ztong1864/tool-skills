# Environment and deployment

## Fixed runtime

- Linux x86-64
- Python 3.10.12
- `admet-ai==1.4.0`
- `chemprop==1.6.1`
- `torch==2.5.0+cpu`
- `rdkit==2024.3.2`
- `numpy==1.26.4`
- `pandas==2.1.4`

Do not use the RDKit 2022.03.5 drug-likeness environment for this skill.

## Offline installation

Create the base environment without a pip subsection:

```bash
conda env create -f environment-base.yml
conda activate admet-prediction
WHEELHOUSE=/path/to/admet_ai_wheels bash scripts/install_offline.sh
```

The installer is intentionally limited to Linux x86-64. It verifies the 68 wheel hashes before calling pip with `--no-index`. The wheel bodies remain on the server and are not included in the skill archive.

`requirements-lock.txt` records the observed environment. `wheels_sha256.txt` is the authoritative integrity manifest for the offline installer. The model checkpoints are installed inside the `admet_ai` package resources.

The source evidence demonstrated inference in the existing server environment but did not demonstrate a separate from-scratch reconstruction. Final acceptance must run the installer in a clean environment or clearly report that reconstruction remains unverified.
