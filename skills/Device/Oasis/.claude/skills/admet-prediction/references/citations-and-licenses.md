# Citations and licenses

## Primary method

- Swanson K, Walther P, Leitz J, Mukherjee S, Wu JC, Shivnaraine RV, Zou J. ADMET-AI: a machine learning ADMET platform for evaluation of large-scale chemical libraries. *Bioinformatics*. 2024. https://doi.org/10.1093/bioinformatics/btae416.
- Official repository: https://github.com/swansonk14/admet_ai.
- This skill fixes the runtime to ADMET-AI v1.4.0 at repository commit `9c8430862b2afd997ff1d314b30bda4418fa9b33`, because the paper and live v1 system differ from the retrained v2 repository head.

## Software and data licensing

- ADMET-AI is distributed under the MIT License; the bundled `LICENSE` is the upstream ADMET-AI license text.
- Chemprop, PyTorch, RDKit, and all transitive packages retain their own licenses.
- Training tasks came from Therapeutics Data Commons. Code/model availability does not automatically grant identical rights for every underlying dataset. Review the relevant TDC dataset terms before redistributing training data or making a commercial-use claim.

In a manuscript, cite the ADMET-AI paper, state version 1.4.0, and identify the individual endpoints used. Do not describe all 98 result fields as 98 independently trained ADMET endpoints.
