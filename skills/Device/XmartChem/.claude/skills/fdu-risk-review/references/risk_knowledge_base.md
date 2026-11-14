# FDU risk review knowledge base

The review checks one thing: whether the materials of a planning artifact (substrates, reagents, catalysts,
additives, solvents, internal standards, work-up liquids), or what they obviously form together, are hazardous
compounds of the tiers below. Experiment details are out of scope (step order, cooling, stirring, work-up, amounts,
units, vessels, device capability, literature support): they never lead to `block` or `needs_human_review`.

Judge membership of a class with chemical knowledge (sodium azide is an azide, triphosgene is a phosgene source).
A material that belongs to neither tier passes; missing SDS data is not a reason to ask.

## Verdict policy

- `block`: a Tier 1 compound is used or obviously formed, and the user has not explicitly confirmed containment,
  protection and approval in this task.
- `needs_human_review`: a Tier 2 compound is used or obviously formed, and the user has not yet confirmed its
  handling and protection in this task. Ask once; after the user confirms, `pass`.
- `pass`: everything else.

## Tier 1: severe acute hazards (`block` unless the user confirmed containment and approval)

- Hydrogen cyanide, or a cyanide source together with acid (NaCN, KCN, CuCN, TMSCN or acetone cyanohydrin with an
  acid or acidic work-up).
- Hydrogen fluoride and free-HF sources (anhydrous HF, HF-pyridine, Et3N·3HF, fluoride salts with strong acid).
- Highly toxic gases used or released: phosgene (also diphosgene, triphosgene), chlorine, hydrogen sulfide, arsine,
  phosphine, diborane, nickel tetracarbonyl, carbon monoxide as a reagent gas, hydrazoic acid.
- Explosive or shock-sensitive compounds: heavy-metal azides, low-molecular organic azides ((C+O)/N < 3), azide with
  acid (HN3) or with dichloromethane (diazidomethane), diazomethane, polynitro aromatics (picric acid, TNT),
  fulminates, concentrated organic peroxides, perchlorate salts heated with organic material, isolated dry
  copper/silver acetylides.
- Pyrophoric reagents: tert-butyllithium, neat trialkylaluminium or diethylzinc, white phosphorus.
- Obviously dangerous combinations: hypochlorite with acid or ammonia, concentrated nitric acid with organic
  solvents, strong oxidiser mixed with strong reducing agent or fuel.

## Tier 2: high hazard (`needs_human_review` until the user confirms handling)

- Water-reactive: alkali metals, NaH, KH, LiAlH4, n-/sec-butyllithium and other organolithium solutions.
- Strong oxidisers in more than catalytic amounts: concentrated HNO3, H2O2 ≥ 30 %, perchloric acid, chromium(VI)
  reagents, permanganate, chlorates.
- Acute toxicity category 1–2: cyanide salts (without acid), mercury and thallium compounds, osmium tetroxide,
  dimethyl sulfate, methyl fluorosulfonate, acrolein, sodium azide.
- Carcinogens of category 1A/1B used as reagents or solvents: benzene, hydrazine, chromium(VI), carbon tetrachloride.
- Strongly corrosive or lachrymatory reagents: oleum, chlorosulfonic acid, thionyl chloride, oxalyl chloride, POCl3,
  bromine.

## Not findings

- Routine catalytic chemistry: Cu(I)/Ag(I) or Zn/Fe/In salts with terminal alkynes in solution (A3/ATA coupling,
  Sonogashira, CuAAC). The acetylide hazard applies to isolating or drying the solids, which these plans do not do.
- Common solvents and work-up liquids (acetonitrile, methanol, ethanol, ethyl acetate, toluene, DCM, THF, DMF, DMSO,
  water), internal standards (biphenyl and the like), molecular sieves, chiral amines and amino-acid derivatives.
- Anything that is an experiment detail rather than a compound (see the first paragraph).

## Boiling point note

For recommendation and amount tables, `scripts/check_boiling_points.py` compares each group's solvent with the
reaction temperature (`KB/solvent_boiling_points.csv`). A `block` result is written into findings as one line,
"提示（不影响结论）：<message>"; it does not change the verdict.
