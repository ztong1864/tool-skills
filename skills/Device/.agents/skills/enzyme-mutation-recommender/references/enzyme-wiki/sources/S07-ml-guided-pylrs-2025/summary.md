# S07 - ML-Guided PylRS Evolution, 2025

PDF: [paper.pdf](paper.pdf)

Original title: "Machine learning-guided evolution of pyrrolysyl-tRNA synthetase for improved incorporation efficiency of diverse noncanonical amino acids"

## Scope

This paper applies supervised and deep learning methods to engineer the tRNA-binding domain of PylRS, using an IFRS catalytic-domain variant as the model system. It is the strongest source for epistasis and scaffold-specific effects among NTD/TBD mutation sets.

## Scaffold And Numbering

- Model scaffold: MmPylRS-derived IFRS, reported as N346I/C348S and selected for 3-iodo-Phe.
- Engineering region: tRNA-binding domain, including NTD, linker, and part of CTD.
- Initial mutation sets tested: R61K/H63Y/S193R, R19H/H29R/T122S, D2N/K3N/T56P/H62Y, and V31I/T56P/H62Y/A100E.
- Com1-IFRS: D2N/V31I/T56P/R61K/H62Y/T122S/S193R on the IFRS background.
- Com2-IFRS: further ML-optimized variant derived from Com1-IFRS; consult the source before using individual added mutations.

## Assays And Substrates

- Main screen: sfGFPS2TAG amber suppression using 3-bromo-Phe as a cheaper proxy for 3-iodo-Phe.
- Kinetics: aminoacylation assays for selected variants, including kcat/Km for tRNA.
- Binding: tRNA(Pyl) affinity measurements for selected WT/Com variants.
- Modeling: AlphaFold-derived structures and molecular dynamics simulations for WT, Com1-WT, and Com2-WT.

## Mutation Evidence

- R19H/H29R/T122S did not produce the expected increase in IFRS.
- IPYE did not improve IFRS in the initial test.
- D2N/K3N/T56P/H62Y increased IFRS stop codon suppression by about sevenfold.
- Among 12 single mutations, D2N, R61K, and H62Y improved IFRS, with D2N strongest.
- Com1-IFRS increased stop codon suppression about elevenfold over IFRS.
- Com2-IFRS increased stop codon suppression about 30.8-fold and improved catalytic efficiency up to 7.8-fold.
- Transplanting Com mutations into seven PylRS-derived synthetases improved yields for six ncAA types.

## Mechanistic Evidence

- Direct evidence: the same mutation sets that work in one scaffold can fail in IFRS, establishing scaffold-context dependence.
- Direct evidence: non-additive interactions were observed; T56P alone reduced activity while T56P/H62Y improved beyond H62Y, indicating positive sign epistasis.
- Direct evidence: ML and saturation studies identified new beneficial positions and strong negative epistasis between some individually beneficial mutations.
- Cross-paper synthesis: tRNA-binding-domain engineering is not a list of universally good residues; it is a coupled fitness landscape conditioned by catalytic pocket, substrate, tRNA, and expression system.

## Caveats

- Main optimization used 3BrF as a proxy substrate; transfer to other substrates is experimentally tested but not automatic for every large or D-form substrate.
- Com2 details should be read from the source before decomposing into single-site recommendations.
- The paper includes code and data availability references; use them if exact variant composition or quantitative tables are needed.

