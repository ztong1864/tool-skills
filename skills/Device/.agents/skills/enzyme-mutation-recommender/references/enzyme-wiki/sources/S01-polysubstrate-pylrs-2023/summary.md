# S01 - Polysubstrate PylRS Variant, 2023

PDF: [paper.pdf](paper.pdf)

Original title: "An evolved pyrrolysyl-tRNA synthetase with polysubstrate specificity expands the toolbox for engineering enzymes with incorporation of noncanonical amino acids"

## Scope

This paper compares MmPylRS(N346A/C348A) with the homologous MbPylRS(N311A/C313A), then improves the Mb variant by combining previously reported N-terminal-domain mutations. The key product is an MbPylRS-derived polysubstrate variant called IPE: N311A/C313A/V31I/T56P/A100E.

## Scaffold And Numbering

- Primary scaffold: Methanosarcina barkeri PylRS.
- Catalytic pocket parent: MbPylRS(N311A/C313A).
- Improved variant: MbPylRS(N311A/C313A/V31I/T56P/A100E), called IPE.
- Homolog comparison: MmPylRS(N346A/C348A), where N346/C348 are homologous active-site positions.
- Numbering must not be merged without mapping: Mb N311/C313 correspond to Mm N346/C348 in this paper's homolog framing.

## Assays And Substrates

- Main readout: sfGFP-R2TAG fluorescence, normalized to cell density, as an amber suppression proxy.
- Initial substrate panel: 12 phenylalanine analogs, including meta-substituted Phe derivatives such as 3-iodo-L-Phe, 3-bromo-L-Phe, 3-methyl-L-Phe, and 3-chloro-L-Phe.
- Extended panel: 43 novel ncAAs tested; 16 were accepted by IPE.
- Application assay: site-specific ncAA incorporation into PedH followed by enzyme characterization and molecular dynamics of PedH, not PylRS.

## Mutation Evidence

- MbPylRS(N311A/C313A) showed higher incorporation efficiency than MmPylRS(N346A/C348A) for all 12 tested Phe analogs.
- IPE combined N311A/C313A with V31I/T56P/A100E and showed broad improvement across diverse ncAAs.
- The selected N-terminal mutations were drawn from prior NTD/TBD studies, but the final combination was optimized in the Mb-NA/CA scaffold.

## Mechanistic Evidence

- Direct evidence: Mb-NA/CA gave higher fluorescence than Mm-NA/CA across the tested panel, supporting scaffold-specific differences in ncAA activation or tRNA charging efficiency.
- Cross-paper synthesis: NTD/TBD mutations can improve incorporation efficiency without directly redesigning the substrate pocket, but their effects are scaffold-specific.
- Context boundary: the paper notes that R19H/H29R/T122S had negligible benefit when transferred to MbPylRS in a separate study, warning against assuming all NTD mutation sets transfer across Methanosarcina origins.

## Caveats

- Many conclusions are based on reporter fluorescence, not purified kinetic constants for every substrate.
- PedH mechanistic interpretation belongs to the engineered target enzyme PedH, not to PylRS mutation recommendation unless the task concerns ncAA effects inside PedH.
- IPE evidence is strongest for MbPylRS(N311A/C313A)-derived polysubstrate systems, not automatically for MmPylRS or D-amino-acid substrates.

