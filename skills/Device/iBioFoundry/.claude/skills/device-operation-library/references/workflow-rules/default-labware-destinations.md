# Default Labware Destinations

Use this rule when a process needs a default destination for a plate, tips box, or balance plate after an operation. These defaults are extracted from validated reference patterns; experiment-specific mappings may override them.

## Tips

- `Tips_MCA*`: high-throughput head tips. When consumed by `FreedomEVO`, route them to waste using `ends 'FreedomEVO:Waste'` in the consuming action container list.
- `Tips_Liha*`: LiHa tips. After use, stage the tips box with `Cytomat_24H [Load]` unless the active experiment mapping sends it somewhere else.

## Plates And Balances

- `Primer1`: after sealing, default to `Cytomat_2C450 [Load]`.
- `PCR_Plate1`: after sealing for low-temperature storage, default to `Cytomat_2C450 [Load]`.
- `PCR_Plate2`: after sealing for low-temperature storage, default to `Cytomat_2C450 [Load]`.
- `Cell_Plate1`: after spreading and sealing, default to `Cytomat_10H [Load]`; for shaking recovery, use the `CYTOMAT_2_Tos` family workflow instead.
- `8Well_Plate_*`: after spreading, default to static incubation in `CYTOMAT_10C [Load]`.
- `Balance_PCR`: after `CentrifugeLoader [Spin]`, default to `Cytomat_24H [Load]`.
- `Balance_DWP*`: after `Rotanta460 [Run]`, default to `Staging_Nests [Load]`.

## Use With Container Rules

Container names must still come from `container-and-status-rules/references/container-catalog.md`. This file only describes likely post-operation destinations and special tip routing syntax.
