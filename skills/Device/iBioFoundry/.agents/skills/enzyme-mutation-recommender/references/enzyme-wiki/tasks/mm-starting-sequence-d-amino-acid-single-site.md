# MmPylRS D-Amino-Acid Saturation-Site Recommendation Task

## Objective

Recommend positions for high-throughput single-site saturation mutagenesis from the starting MmPylRS-like sequence. The current scope is N-terminal / tRNA-binding-domain engineering unless the user later expands the search space.

The experimental goal is to improve catalytic activity toward at least one bulky or halogenated D-amino-acid substrate and discover a site where one of the 19 amino acid replacements yields drastic or breakthrough activity enhancement.

## Current Target Substrates

- D-F
- D-3ClF
- D-3BrF
- D-3CF3F
- D-4CH3F

## Recommendation Constraints

- Recommend positions for saturation mutagenesis, not a fixed replacement amino acid, unless the user explicitly asks for exact substitutions.
- For each recommended position, report the current amino acid in the starting sequence.
- Literature substitutions should be listed only as evidence anchors explaining why the position is worth scanning.
- The experimental action for a recommended position is to test all 19 non-native amino acid replacements at that position.
- Prefer N-terminal / tRNA-binding-domain candidates unless the user later expands scope.
- Treat the starting sequence as the chassis; do not recommend reverting known chassis mutations unless explicitly asked.
- Cite Wiki evidence for every candidate site.
- State whether support is direct evidence, cross-paper synthesis, or exploratory extrapolation.
- Direct evidence for the listed bulky / halogenated D-form Phe-like substrates is limited or absent in the initial Wiki, so recommendation claims must be cautious and mechanism-derived.
- Do not add concrete recommendations to this task page until a recommendation round is actually performed.

## Wild-Type Reference Sequence

Scaffold: MmPylRS wild type.

```text
MDKKPLNTLISATGLWMSRTGTIHKIKHHEVSRSKIYIEMACGDHLVVNNSRSSRTARALRHHKYRKTCKRCRVSDEDLNKFLTKANEDQTSVKVKVVSAPTRTKKAMPKSVARAPKPLENTEAAQAQPSGSKFSPAIPVSTQESVSVPASVSTSISSISTGATASALVKGNTNPITSMSAPVQASAPALTKSQTDRLEVLLNPKDEISLNSGKPFRELESELLSRRKKDLQQIYAEERENYLGKLEREITRFFVDRGFLEIKSPILIPLEYIERMGIDNDTELSKQIFRVDKNFCLRPMLAPNLYNYLRKLDRALPDPIKIFEIGPCYRKESDGKEHLEEFTMLNFCQMGSGCTRENLESIITDFLNHLGIDFKIVGDSCMVYGDTLDVMHGDLELSSAVVGPIPLDREWGIDKPWIGAGFGLERLLKVKHDFKNIKRAARSESYYNGISTNL*
```

## Starting Sequence

```text
MDKKPLNTLISATGLWMSRTGTIHKIKHHEVSRSKIYIEMACGDHLVVNNSRSSRTARALRHHKYRKTCKRCRVSDEDLNKFLTKANEDQTSVKVKVVSAPTRTKKAMPKSVARAPKPLENTEAAQAQPSGSKFSPAIPVSTQESVSVPASVSTSISSISTGATASALVKGNTNPITSMSAPVQASAPALTKSQTDRLEVLLNPKDEISLNSGKPFRELESELLSRRKKDLQQIYAEERENYLGKLEREITRFFVDRGFLEIKSPILIPLEYIERMGIDNDTELSKQIFRVDKNFCLRPMLAPNLYNYLRKLDRALPDPIKIFEIGPCYRKESDGKEHLEEFTMLGFQQMGSGCTRENLESIITDFLNHLGIDFKIVGDSCMVYGDTLDVMHGDLELSSAGVGPIPLDREWGIDKPWIGAGFGLERLLKVKHDFKNIKRAARSESYYNGISTNL*
```

## Initial Chassis Summary

- Sequence length: 455 residues including terminal `*`.
- Length relative to WT: same length.
- Existing substitutions relative to WT:
  - N346G
  - C348Q
  - V401G
- `N346/C348` are catalytic-pocket positions in the general Wiki and should be treated as part of the current substrate-recognition chassis.
- `V401G` is outside the current N-terminal/TBD focus but remains part of the chassis state and should be retained in sequence alignment and recommendation reasoning.

## Recommendation Round History

No recommendation round has been run yet.

## Experimental Feedback History

Use this schema when results are available.

| Round id | Date | Saturated site | Best replacement(s), if any | Full chassis background | Substrate(s) | Assay/readout | Relative activity or qualitative outcome | Notes and follow-up implication | Wiki update needed |
|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  |
