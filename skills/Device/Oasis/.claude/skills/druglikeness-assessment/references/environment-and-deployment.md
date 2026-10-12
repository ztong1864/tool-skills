# Environment and deployment

## Tested scientific runtime

- Linux x86-64, CentOS 7 server
- Python 3.10.12
- RDKit 2022.03.5
- pandas 2.0.3
- NumPy 1.25.0

Create an environment with:

```bash
conda env create -f environment.yml
conda activate druglikeness
```

The environment file has no machine-specific `prefix`. The original server evidence validated inference in an existing environment and after a same-filesystem environment copy; it did not prove a from-scratch cross-machine reconstruction. Treat fresh environment creation as a server acceptance item.

The Python wrapper contains no absolute runtime path. Run it from any location by using explicit input and output paths.

The bundled version has not been validated on macOS arm64. Do not infer portability solely from conda metadata.
