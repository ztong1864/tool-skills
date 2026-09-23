# Mutation Evidence Matrix

This matrix is the primary lookup table for recommendation. Each row is an evidence unit, not a universal rule.

| Evidence id | Mutation or set | Original scaffold | Numbering | Substrate | Assay/readout | Observed effect | Mechanism status | Sources |
|---|---|---|---|---|---|---|---|---|
| M01 | N311A/C313A | MbPylRS | Mb | 12 L-Phe analogs | sfGFP-R2TAG fluorescence | Higher activity than Mm N346A/C348A for all 12 tested ncAAs | Direct effect; mechanism inferred as scaffold/catalytic efficiency difference | [S01](../sources/S01-polysubstrate-pylrs-2023/summary.md) |
| M02 | N346A/C348A | MmPylRS | Mm | Phe analogs | sfGFP-R2TAG fluorescence | Broad substrate scope but lower activity than Mb homolog in S01 comparison | Active-site pocket evidence; lower efficiency context | [S01](../sources/S01-polysubstrate-pylrs-2023/summary.md) |
| M03 | V31I/T56P/A100E on Mb N311A/C313A | Mb-NA/CA | Mb | diverse ncAAs, Phe analogs | sfGFP fluorescence | IPE improves polysubstrate incorporation and accepts many additional ncAAs | Cross-paper synthesis: NTD/TBD improvement on Mb polysubstrate pocket | [S01](../sources/S01-polysubstrate-pylrs-2023/summary.md) |
| M04 | V31I/T56P/H62Y/A100E | chPylRS | chimeric | BocK | PACE, luciferase, sfGFP, kinetics | Large catalytic efficiency and reporter improvements; transfers to several PylRS variants | Direct activity evidence; NTD/TBD mechanism inferred | [S03](../sources/S03-pace-aaRS-2017/summary.md) |
| M05 | D2N/K3N/T56P/H62Y | chPylRS/Mm NTD context | source | BocK, Pyl | crystallography, kinetics | Alters tRNA contacts; full evolved variants improve BocK-related activity | Direct structural mechanism: weakened NTD-tRNA contacts plus compensated CTD recognition | [S04](../sources/S04-pylrs-ntd-structure-2017/summary.md) |
| M06 | R19H/H29R/T122S | MmPylRS | Mm | BocK | sfGFP134TAG, SDS-PAGE | About fourfold higher sfGFP expression vs WT | Direct activity evidence; mechanism unresolved in source | [S05](../sources/S05-evolving-ntd-2018/summary.md) |
| M07 | R19H/H29R/T122S transferred to AcKRS | Mm-derived AcKRS | Mm-derived | AcK | sfGFP, H3K23ac yield | H3K23ac yield improved from 3.7 to 9.4 mg/L | Direct transfer evidence; mechanism unresolved | [S05](../sources/S05-evolving-ntd-2018/summary.md) |
| M08 | R19H/H29R/T122S transferred to AcdKRS | Mm-derived AcdKRS | Mm-derived | AcdK | sfGFP | About 20% improvement | Direct transfer evidence; substrate/process dependence | [S05](../sources/S05-evolving-ntd-2018/summary.md) |
| M09 | R61K/H63Y/S193R | MmPylRS | Mm | S-benzyl Cys analogs, N-pi-methyl-His, others | sfGFP-UAG2/UAG27, MS | Shifts substrate range and improves selected incorporation outcomes | Source inference: remote tRNA-interface tuning | [S06](../sources/S06-linker-ntd-engineering-2020/summary.md) |
| M10 | GGGGS-type linker insertions between P149/A150 | MmPylRS and ZRS | Mm | multiple ncAAs | sfGFP reporters, western blot | Moderate linker effects can improve or alter activity depending on scaffold | Cross-paper synthesis: NTD/CTD/tRNA geometry tuning | [S06](../sources/S06-linker-ntd-engineering-2020/summary.md) |
| M11 | R19H/H29R/T122S in IFRS | IFRS | Mm-derived | 3BrF | sfGFPS2TAG fluorescence | Did not achieve expected increase | Context boundary; scaffold-specific failure | [S07](../sources/S07-ml-guided-pylrs-2025/summary.md) |
| M12 | V31I/T56P/H62Y/A100E in IFRS | IFRS | Mm-derived | 3BrF | sfGFPS2TAG fluorescence | Did not improve IFRS in initial test | Context boundary; scaffold-specific failure | [S07](../sources/S07-ml-guided-pylrs-2025/summary.md) |
| M13 | D2N/K3N/T56P/H62Y in IFRS | IFRS | Mm-derived | 3BrF | sfGFPS2TAG fluorescence | About sevenfold SCS improvement | Direct activity evidence; epistasis within set | [S07](../sources/S07-ml-guided-pylrs-2025/summary.md) |
| M14 | D2N, R61K, H62Y singles | IFRS | Mm-derived | 3BrF | sfGFPS2TAG fluorescence | Only these three among 12 singles improved IFRS; D2N strongest | Direct single-site evidence in IFRS | [S07](../sources/S07-ml-guided-pylrs-2025/summary.md) |
| M15 | Com1-IFRS: D2N/V31I/T56P/R61K/H62Y/T122S/S193R | IFRS | Mm-derived | 3BrF | sfGFPS2TAG fluorescence | About elevenfold SCS improvement | Direct combinatorial evidence; strong epistasis | [S07](../sources/S07-ml-guided-pylrs-2025/summary.md) |
| M16 | Com2-IFRS | IFRS | Mm-derived | diverse ncAAs | SCS, kinetics, transfer tests | About 30.8-fold SCS improvement; up to 7.8-fold catalytic efficiency improvement | Direct combinatorial evidence; exact composition requires source lookup | [S07](../sources/S07-ml-guided-pylrs-2025/summary.md) |
| M17 | V8E/T13I/I36V/H45L/S121R/I355T | Mb CrtK-RS | Mb/CrtK | CrtK | LacZ, beta-gal, YFP, MS | 250-370% higher CrtK incorporation depending on assay | Direct activity evidence; mechanism unresolved, likely tRNA/cellular interaction | [S08](../sources/S08-two-tier-screening-2017/summary.md) |
| M18 | V8E/T13I/I36V/H45L/S121R/I355T transferred to AynK-RS | Mb AynK-RS | Mb/AynK | AynK | YFP(TAG) | About 2.2-fold expression improvement | Direct transfer evidence in related lysine analog scaffold | [S08](../sources/S08-two-tier-screening-2017/summary.md) |

## Use Rules

- Exploitation candidates require a row with matching or alignable scaffold, matching substrate class, and compatible assay.
- Exploration candidates may use mechanism pages, but must cite the evidence rows that generated the mechanism.
- Rows M11 and M12 are negative evidence and must be considered when transferring mutation sets into IFRS-like backgrounds.

