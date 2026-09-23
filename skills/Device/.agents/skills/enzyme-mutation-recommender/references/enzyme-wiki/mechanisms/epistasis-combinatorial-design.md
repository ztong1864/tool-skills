# Epistasis And Combinatorial Design

## Direct Evidence

- [S07](../sources/S07-ml-guided-pylrs-2025/summary.md) reports that D2N and H62Y individually improve IFRS, while K3N and T56P individually reduce activity, yet D2N/K3N/T56P/H62Y improves IFRS strongly.
- [S07](../sources/S07-ml-guided-pylrs-2025/summary.md) reports positive sign epistasis and negative reciprocal sign epistasis among TBD mutations.
- [S07](../sources/S07-ml-guided-pylrs-2025/summary.md) shows that combinations predicted from a small learned fitness landscape can outperform naive addition of single-site effects.

## Cross-Paper Synthesis

- Single-site recommendation should not ignore known epistasis. A single mutation that is beneficial in one background can be harmful or neutral in another.
- For "single-site from a starting sequence" tasks, the existing mutations in the user's chassis determine which evidence row is relevant.
- If a user sequence already contains several TBD mutations, recommend a site by comparing the chassis to the closest documented combinatorial background rather than to wild type.

## Recommendation Implication

Report both standalone evidence and background-dependent risk. If the Wiki evidence is combinatorial but the task asks for single-site mutations, identify which single change moves the user's current sequence toward a documented high-performing combination and explain the uncertainty.

