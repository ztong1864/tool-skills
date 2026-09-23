# MOF KB 知识索引（V3）

> 最后更新：2026-04-28T14:29:23Z
> build_id: build_20260428_142902

---

## 概览

- 论文总数：274
- EvidenceTrace：（来自索引）
- MaterialDossier：676（完整：201，不完整：475）
- DesignRuleCard：811 | ComparativeFindingCard：862 | FailureCaseCard：518
- CandidateCompositionTuple：0（core：0，expanded：0，frontier：0）
- TaskPlaybook：9
- Skilllet：0（empirical：0，prior：0，hybrid：0）
- LigandSignature：191 | PillarSignature：97 | NodeSignature：92
- MeasurementCard：1478 | TopologyCompatibilityCard：55

---

## 任务页（TaskPage）

| 任务 | 论文数 | Playbook | Candidate Tuples | 设计规则数 | 覆盖质量 |
|------|--------|----------|-----------------|-----------|----------|
| [[tasks/Xe_Kr_separation]] | 1 | 1 | 0 | 2 | sparse |
| [[tasks/C3H6_C3H8_separation]] | 10 | 1 | 0 | 30 | good |
| [[tasks/CO2_N2_separation]] | 22 | 1 | 0 | 85 | good |
| [[tasks/C2H4_C2H6_separation]] | 2 | 1 | 0 | 4 | sparse |
| [[tasks/H2_storage]] | 5 | 1 | 0 | 19 | good |
| [[tasks/gas_separation]] | 121 | 1 | 0 | 311 | good |
| [[tasks/CO2_capture]] | 72 | 1 | 0 | 228 | good |
| [[tasks/C2H2_C2H4_separation]] | 23 | 1 | 0 | 88 | good |
| [[tasks/C2H2_CO2_separation]] | 17 | 1 | 0 | 68 | good |

---

## 候选组合（CandidateCompositionTuple）

| 组合 | 金属 | 配体 | 柱撑体 | 拓扑 | 金属源 | 置信度 | 证据分 | 层级 |
|------|------|------|--------|------|--------|--------|--------|------|
| （暂无）| - | - | - | - | - | - | - | - |

---

## 设计规则（DesignRuleCard）

| 规则 | 任务 | 干预 | 效果 | 置信度 | 详见 |
|------|------|------|------|--------|------|
| drule_826500 | C2H2_C2H4_separation | use a wall-trapped C2H2 tetramer arrangement in th | can effectively promote kinetic behavior | 0.70 | [[rules/drule_826500363f13]] |
| drule_3e0f03 | CO2_capture | use pore and aperture tuning engineering in MOF de | used as a strategy to precisely trap CO2 | 0.70 | [[rules/drule_3e0f03ba11db]] |
| drule_4a34d5 | CO2_N2_separation | select adsorbents that combine high CO2 capacity,  | preferred for reducing energy consumptio | 0.70 | [[rules/drule_4a34d5ea2951]] |
| drule_781d25 | CO2_capture | install halogen-bond donor and acceptor groups ont | reduces assembly variables and is presen | 0.70 | [[rules/drule_781d251d0de0]] |
| drule_ec941b | gas_separation | manipulate local chemistry, including metal and li | enables design and tuning of desired the | 0.70 | [[rules/drule_ec941b19d02f]] |
| drule_8793b8 | gas_separation | replace DMF with DEF under otherwise identical syn | a different phase, 1′, is isolated inste | 0.70 | [[rules/drule_8793b8bcd9b4]] |
| drule_09357c | gas_separation | vary solvent medium, concentration, temperature, h | crystal morphology, particle size, cryst | 0.70 | [[rules/drule_09357c104595]] |
| drule_d14063 | gas_separation | load β-PCMOF2 pores with less volatile, amphiproti | successfully enhanced anhydrous proton c | 0.70 | [[rules/drule_d14063c7e065]] |
| drule_1a4f07 | CO2_capture | pre-functionalize the MAC-4 linker with hydroxyl g | CO2 uptake is significantly enhanced in  | 0.70 | [[rules/drule_1a4f071845cb]] |
| drule_2da0dc | CO2_capture | incorporate dense and strong multiple CO2 binding  | produces ultrastrong CO2 binding affinit | 0.70 | [[rules/drule_2da0dc437415]] |
| drule_c5e5ae | C2H2_C2H4_separation | introduce aromatic-based rings to create C-H bindi | affords higher C2H2 and C2H6 affinity th | 0.70 | [[rules/drule_c5e5aec60537]] |
| drule_85a0b1 | gas_separation | operate phosphate adsorption at pH 3 | pH 3 was identified as the optimal pH | 0.70 | [[rules/drule_85a0b1c9712b]] |
| drule_c76e70 | Xe_Kr_separation | design CALF-20-like cavities with a suitable size  | identified as a suitable cavity-size fea | 0.70 | [[rules/drule_c76e70ed16f2]] |
| drule_1fe8ce | C2H2_C2H4_separation | introduce adjacent uncoordinated carboxylate-O ato | promotes preferential recognition of C2H | 0.70 | [[rules/drule_1fe8cea56667]] |
| drule_04e278 | C3H6_C3H8_separation | use a local shrinkage feature instead of only narr | improves the likelihood of maintaining d | 0.70 | [[rules/drule_04e278d3ce4c]] |
| drule_a1e176 | gas_separation | use rigid carboxylate ligands to bridge 2D layers  | is described as one of the most rational | 0.70 | [[rules/drule_a1e1767005f8]] |
| drule_cea3d4 | CO2_capture | sterically shield Zn2+ sites with surrounding link | hydrolytic stability is enhanced and wat | 0.70 | [[rules/drule_cea3d4855333]] |
| drule_904950 | gas_separation | design Zn(II)-uniconazole complexes with smaller H | complexes 1-4 have HOMO-LUMO gaps of 0.0 | 0.70 | [[rules/drule_904950380b15]] |
| drule_7bbaa0 | C2H2_CO2_separation | introduce molecular rotors as dynamic pillar ligan | enables controllable reverse and non-rev | 0.70 | [[rules/drule_7bbaa0ddc2a3]] |
| drule_0e0ec3 | CO2_capture | use larger-pore frameworks for small molecules | small molecules generally show significa | 0.70 | [[rules/drule_0e0ec3482ff5]] |

---

## 论文摘要页（SourcePage）

| 论文 | 任务 | 材料数 | 设计规则数 | 摄入日期 |
|------|------|--------|-----------|----------|
| [[sources/3bb15c92cc7b\|3bb15c92cc7b]] | CO2_capture | 4 | 2 | 2026-04-24 |
| [[sources/ee237b02c72e\|New luminescent Zn(II) compound as a hig]] | gas_separation | 2 | 1 | 2026-04-24 |
| [[sources/8199cbc71be5\|8199cbc71be5]] | gas_separation | 1 | 3 | 2026-04-24 |
| [[sources/0c2479715990\|0c2479715990]] | C2H2_C2H4_separation | 4 | 3 | 2026-04-24 |
| [[sources/8453eeb895d8\|8453eeb895d8]] | CO2_capture | 3 | 3 | 2026-04-24 |
| [[sources/5fdf9f5f0fbd\|Synergistic sorbent separation for one-s]] | C2H2_C2H4_separation | 4 | 5 | 2026-04-24 |
| [[sources/35fcf2cf447e\|35fcf2cf447e]] | gas_separation | 1 | 5 | 2026-04-24 |
| [[sources/9621c008066d\|Four Zn(II)Cd(II)-3-amino-1,2,4-triazola]] | gas_separation | 4 | 5 | 2026-04-24 |
| [[sources/0980bd5892a8\|Efficient Xe selective separation from X]] | Xe_Kr_separation | 6 | 2 | 2026-04-24 |
| [[sources/d9b80005c58d\|d9b80005c58d]] | gas_separation | 9 | 4 | 2026-04-24 |
| [[sources/fd11547b34e2\|Humidity-Responsive Polymorphism in CALF]] | CO2_capture | 1 | 2 | 2026-04-24 |
| [[sources/5d8eca38aab2\|Wall-trapped acetylene tetramer in a met]] | C2H2_C2H4_separation | 0 | 3 | 2026-04-24 |
| [[sources/df399a767a7e\|df399a767a7e]] | gas_separation | 2 | 3 | 2026-04-24 |
| [[sources/e4f2dd03ed6d\|e4f2dd03ed6d]] | gas_separation | 6 | 1 | 2026-04-24 |
| [[sources/f99adb3f4b07\|An electrochemically neutralized energy-]] | gas_separation | 1 | 2 | 2026-04-24 |
| [[sources/adc30d5190af\|adc30d5190af]] | gas_separation | 5 | 7 | 2026-04-24 |
| [[sources/327e4c63e7dd\|A zinc(II) metal–organic framework based]] | gas_separation | 1 | 1 | 2026-04-24 |
| [[sources/a5f035406a01\|Pore configuration control in hybrid azo]] | C3H6_C3H8_separation | 3 | 2 | 2026-04-24 |
| [[sources/fd9300073a96\|fd9300073a96]] | C2H2_C2H4_separation | 3 | 4 | 2026-04-24 |
| [[sources/e990e0e8c588\|e990e0e8c588]] | gas_separation | 3 | 0 | 2026-04-24 |
| [[sources/3ffa6c8bb295\|Exceptionally Stable, Hollow Tubular Met]] | gas_separation | 4 | 0 | 2026-04-24 |
| [[sources/2d345c000268\|H4betc-A stable, pillar-layer metal–orga]] | gas_separation | 1 | 3 | 2026-04-24 |
| [[sources/234cd07539aa\|IPA-F]] | C2H4_C2H6_separation | 1 | 3 | 2026-04-24 |
| [[sources/b612f8927383\|High CO2 and H2 Uptake in an Anionic Por]] | CO2_N2_separation | 1 | 3 | 2026-04-24 |
| [[sources/1ab646fccf23\|1ab646fccf23]] | gas_separation | 6 | 2 | 2026-04-24 |
| [[sources/4ebb439e73d2\|4ebb439e73d2]] | gas_separation | 7 | 3 | 2026-04-24 |
| [[sources/9a91aa096117\|Framework Enabling Benchmark Inverse Sel]] | C2H2_CO2_separation | 2 | 1 | 2026-04-24 |
| [[sources/45f9abb3ad1c\|45f9abb3ad1c]] | gas_separation | 3 | 2 | 2026-04-24 |
| [[sources/7002be9dcc15\|Strong and Dynamic CO2 Sorption in a Fle]] | CO2_capture | 2 | 5 | 2026-04-24 |
| [[sources/0f9f2bdd54db\|0f9f2bdd54db]] | gas_separation | 1 | 2 | 2026-04-24 |
| [[sources/bfa7c9affeb8\|Zn Metal–Organic Framework with High Sta]] | CO2_capture | 2 | 1 | 2026-04-24 |
| [[sources/de52aa10b4d9\|Direct Determination of the Single-Ion A]] | gas_separation | 6 | 1 | 2026-04-24 |
| [[sources/39219513efa5\|3D zinc(II) coordination polymers built ]] | gas_separation | 3 | 0 | 2026-04-24 |
| [[sources/930aff59a5dd\|A scalable ultramicroporous metal-organi]] | C3H6_C3H8_separation | 2 | 2 | 2026-04-24 |
| [[sources/98d9e3d44821\|98d9e3d44821]] | gas_separation | 2 | 3 | 2026-04-24 |
| [[sources/d3f7c46a759d\|Novel HBD-Containing Zn (dobdc) (datz) a]] | CO2_capture | 2 | 4 | 2026-04-24 |
| [[sources/6cff4bbbe500\|Precise regulating synergistic effect in]] | H2_storage | 8 | 3 | 2026-04-24 |
| [[sources/d87085de1c1d\|d87085de1c1d]] | gas_separation | 8 | 2 | 2026-04-24 |
| [[sources/653921058bc6\|Poly[bis(μ 3 -3-amino-1,2,4-triazolato)]] | gas_separation | 1 | 2 | 2026-04-24 |
| [[sources/95c5e1a4b5d9\|X-TRZSmall - 2024 - Yang - Shifting C2H2]] | C2H2_CO2_separation | 4 | 3 | 2026-04-24 |
| [[sources/6067608ce1e2\|Carbon Dioxide Capture in a Carbonate-Pi]] | CO2_capture | 3 | 4 | 2026-04-24 |
| [[sources/34af98065e7b\|A novel water-stable MOF Zn(Py)(Atz) as ]] | CO2_capture | 1 | 4 | 2026-04-24 |
| [[sources/bb3ea0ef2139\|bb3ea0ef2139]] | CO2_capture | 2 | 2 | 2026-04-24 |
| [[sources/f4ee8ef5453e\|Exploring the Potential of a Highly Scal]] | CO2_N2_separation | 7 | 5 | 2026-04-24 |
| [[sources/2e9e333299b2\|Immobilization of the Polar Group into a]] | C2H2_CO2_separation | 2 | 6 | 2026-04-24 |
| [[sources/3fdc7853db6d\|3fdc7853db6d]] | gas_separation | 1 | 1 | 2026-04-24 |
| [[sources/987bc8a29237\|Studies on the removal of phosphate in w]] | gas_separation | 6 | 2 | 2026-04-24 |
| [[sources/40718dae876e\|40718dae876e]] | CO2_capture | 12 | 4 | 2026-04-24 |
| [[sources/122d7b4e0d01\|Isoreticular Three-Dimensional Kagome Me]] | C2H2_CO2_separation | 2 | 3 | 2026-04-24 |
| [[sources/97878d3357f1\|97878d3357f1]] | gas_separation | 2 | 7 | 2026-04-24 |
| [[sources/526b137a4e63\|H2FA-Hydrogen bond unlocking-driven pore]] | C2H2_C2H4_separation | 3 | 3 | 2026-04-24 |
| [[sources/3642cdd42737\|3642cdd42737]] | gas_separation | 0 | 3 | 2026-04-24 |
| [[sources/509de9186208\|509de9186208]] | CO2_capture | 2 | 0 | 2026-04-24 |
| [[sources/c1a5d8e02c30\|Construction of a New Co(II) Coordinatio]] | gas_separation | 2 | 3 | 2026-04-24 |
| [[sources/9d7addf6cc90\|SO4]] | C3H6_C3H8_separation | 4 | 3 | 2026-04-24 |
| [[sources/28c83b15b1b5\|H2IPA]] | CO2_capture | 2 | 2 | 2026-04-24 |
| [[sources/3a2a3169d968\|Post-Combustion CO2 capture by vacuum sw]] | CO2_capture | 3 | 4 | 2026-04-24 |
| [[sources/99abd74c416a\|Construction of a bifunctional Zn(II)–or]] | CO2_capture | 2 | 2 | 2026-04-24 |
| [[sources/b2bd48fc9577\|Residence time distribution in fluidized]] | CO2_capture | 7 | 3 | 2026-04-24 |
| [[sources/a0e9f0acf0bb\|New luminescent Zn(II) compound as a hig]] | gas_separation | 2 | 3 | 2026-04-24 |
| [[sources/6f6e2157a8fd\|PO4-trzAngew Chem Int Ed - 2025 - Sarkar]] | gas_separation | 10 | 2 | 2026-04-24 |
| [[sources/23635e636118\|Synthesis and characterization of two ne]] | gas_separation | 1 | 8 | 2026-04-24 |
| [[sources/bfbed74e28fe\|bfbed74e28fe]] | CO2_capture | 9 | 3 | 2026-04-24 |
| [[sources/8fafae7223b5\|8fafae7223b5]] | CO2_N2_separation | 3 | 0 | 2026-04-24 |
| [[sources/7079b11fb224\|H2FA-Xing 等。 - 2015 - Microporous Zinc(I]] | CO2_capture | 1 | 2 | 2026-04-24 |
| [[sources/80889541cbf7\|Pore Surface Tailored SOD-Type Metal-Org]] | gas_separation | 11 | 1 | 2026-04-24 |
| [[sources/9fbde6b04aa6\|9fbde6b04aa6]] | C3H6_C3H8_separation | 3 | 5 | 2026-04-24 |
| [[sources/8a689977d757\|8a689977d757]] | gas_separation | 1 | 3 | 2026-04-24 |
| [[sources/94d0484540b0\|Construction of a zeolite A-type multiva]] | gas_separation | 2 | 5 | 2026-04-24 |
| [[sources/266d29fc0075\|266d29fc0075]] | gas_separation | 2 | 3 | 2026-04-24 |
| [[sources/fa7473797f58\|fa7473797f58]] | gas_separation | 2 | 3 | 2026-04-24 |
| [[sources/be82c3858dd0\|An electrochemically neutralized energy-]] | gas_separation | 1 | 3 | 2026-04-24 |
| [[sources/05f5cdef9b49\|A {Zn 5 } cluster‐based metal–organic f]] | gas_separation | 5 | 3 | 2026-04-24 |
| [[sources/f409ad2e178a\|f409ad2e178a]] | gas_separation | 2 | 5 | 2026-04-24 |
| [[sources/79ccfb53a022\|A zinc(II) metal–organic framework based]] | gas_separation | 2 | 1 | 2026-04-24 |
| [[sources/8bf7f8c8aa14\|A Highly Stable Framework of Crystalline]] | gas_separation | 3 | 2 | 2026-04-24 |
| [[sources/25a1e70b986d\|Novel Iso-Reticular Zn(II) Metal–Organic]] | CO2_capture | 2 | 3 | 2026-04-24 |
| [[sources/0d9c5712fee6\|A self-catenated rob-type porous coordin]] | CO2_capture | 5 | 3 | 2026-04-24 |
| [[sources/b371e84f5f09\|b371e84f5f09]] | gas_separation | 2 | 1 | 2026-04-24 |
| [[sources/40b04428835f\|Preferential CO 2 adsorption by an ultr]] | CO2_capture | 4 | 5 | 2026-04-24 |
| [[sources/f55a02c26322\|f55a02c26322]] | CO2_N2_separation | 1 | 2 | 2026-04-24 |
| [[sources/6baaaba11f24\|A Flexible Porous MOF Exhibiting Reversi]] | gas_separation | 2 | 1 | 2026-04-24 |
| [[sources/286e012e968f\|286e012e968f]] | C2H2_C2H4_separation | 1 | 2 | 2026-04-24 |
| [[sources/2051063a5ece\|2051063a5ece]] | gas_separation | 1 | 1 | 2026-04-24 |
| [[sources/f8402f8ea542\|f8402f8ea542]] | gas_separation | 13 | 8 | 2026-04-24 |
| [[sources/625603ff8379\|H2bdc]] | CO2_N2_separation | 1 | 3 | 2026-04-24 |
| [[sources/2c0d01aac737\|2c0d01aac737]] | CO2_N2_separation | 1 | 0 | 2026-04-24 |
| [[sources/8a61649cf87e\|A Series of Metal–Organic Frameworks Bui]] | CO2_capture | 16 | 4 | 2026-04-24 |
| [[sources/f70ee3da2e06\|f70ee3da2e06]] | gas_separation | 1 | 2 | 2026-04-24 |
| [[sources/08169a547bbc\|08169a547bbc]] | CO2_N2_separation | 7 | 1 | 2026-04-24 |
| [[sources/3f79bf505f33\|3f79bf505f33]] | gas_separation | 3 | 4 | 2026-04-24 |
| [[sources/cd9897204eef\|Abnormal CO2 and H2O Diffusion in CALF-2]] | CO2_capture | 1 | 1 | 2026-04-24 |
| [[sources/86a7c025866c\|86a7c025866c]] | CO2_capture | 1 | 1 | 2026-04-24 |
| [[sources/c4a33fca36cb\|Synthesis and characterization of two ne]] | gas_separation | 3 | 2 | 2026-04-24 |
| [[sources/e7bb127fff1a\|e7bb127fff1a]] | gas_separation | 5 | 2 | 2026-04-24 |
| [[sources/d3cb3f2fb120\|d3cb3f2fb120]] | H2_storage | 7 | 4 | 2026-04-24 |
| [[sources/ab2f2ea89067\|Ligand Symmetry Modulation for Designing]] | C2H2_CO2_separation | 1 | 4 | 2026-04-24 |
| [[sources/cccbb8ebbffc\|A scalable robust microporous Al-MOF for]] | CO2_capture | 3 | 4 | 2026-04-24 |
| [[sources/f13b85af5e0f\|Isoreticular Three-Dimensional Kagome Me]] | C2H2_CO2_separation | 3 | 4 | 2026-04-24 |
| [[sources/d0656fee58b5\|Three Zn(II)-triazole-H3btc complexes re]] | gas_separation | 3 | 2 | 2026-04-24 |
| [[sources/b2a9adbbc4b4\|b2a9adbbc4b4]] | gas_separation | 2 | 0 | 2026-04-24 |
| [[sources/a3ea5d899378\|a3ea5d899378]] | gas_separation | 6 | 3 | 2026-04-24 |
| [[sources/6b310008b988\|6b310008b988]] | C2H2_CO2_separation | 3 | 3 | 2026-04-24 |
| [[sources/585d1cd3111b\|Charting the CO2 capture performance of ]] | CO2_N2_separation | 1 | 0 | 2026-04-24 |
| [[sources/f297c1f73265\|f297c1f73265]] | H2_storage | 3 | 5 | 2026-04-24 |
| [[sources/42a2825a2090\|Preferential CO 2 adsorption by an ultr]] | CO2_capture | 3 | 5 | 2026-04-24 |
| [[sources/530f5c40e426\|A new anionic metal–organic framework sh]] | CO2_capture | 4 | 2 | 2026-04-24 |
| [[sources/1cdb348c09d0\|1cdb348c09d0]] | C2H2_CO2_separation | 3 | 5 | 2026-04-24 |
| [[sources/47bd0617ba03\|Separation of CO2 and N2 on a hydrophobi]] | CO2_N2_separation | 2 | 4 | 2026-04-24 |
| [[sources/014124fe711e\|014124fe711e]] | CO2_capture | 1 | 3 | 2026-04-24 |
| [[sources/1f71b819131c\|Two isostructural amine-functionalized 3]] | CO2_N2_separation | 1 | 2 | 2026-04-24 |
| [[sources/92ab82a51655\|Abnormal CO2 and H2O Diffusion in CALF-2]] | CO2_capture | 1 | 1 | 2026-04-24 |
| [[sources/93123c5868a2\|93123c5868a2]] | gas_separation | 2 | 8 | 2026-04-24 |
| [[sources/4b169130f161\|Zeolitic metal azolate frameworks (MAFs)]] | gas_separation | 11 | 5 | 2026-04-24 |
| [[sources/8eeb28d8abfa\|8eeb28d8abfa]] | C3H6_C3H8_separation | 2 | 6 | 2026-04-24 |
| [[sources/6f088017d1f9\|6f088017d1f9]] | gas_separation | 3 | 2 | 2026-04-24 |
| [[sources/47e14342870f\|47e14342870f]] | CO2_capture | 7 | 3 | 2026-04-24 |
| [[sources/7173aa00e955\|7173aa00e955]] | gas_separation | 5 | 4 | 2026-04-24 |
| [[sources/22272f44e8c7\|22272f44e8c7]] | CO2_capture | 4 | 3 | 2026-04-24 |
| [[sources/4aac5875b0eb\|4aac5875b0eb]] | C2H4_C2H6_separation | 1 | 1 | 2026-04-24 |
| [[sources/a5965e89e460\|A new anionic metal–organic framework sh]] | CO2_capture | 4 | 2 | 2026-04-24 |
| [[sources/524fd695803c\|524fd695803c]] | CO2_capture | 2 | 3 | 2026-04-24 |
| [[sources/c6c12319f7ad\|Tailoring Hydrophobicity and Pore Enviro]] | CO2_capture | 3 | 3 | 2026-04-24 |
| [[sources/12b2852ac256\|Green and Scalable Preparation of an Iso]] | C3H6_C3H8_separation | 2 | 1 | 2026-04-24 |
| [[sources/57f7dc1dff2e\|Four Novel Three-Dimensional Pillared-La]] | gas_separation | 3 | 4 | 2026-04-24 |
| [[sources/bff26f8ebf7c\|bff26f8ebf7c]] | CO2_N2_separation | 2 | 2 | 2026-04-24 |
| [[sources/4bf71c012a6c\|4bf71c012a6c]] | gas_separation | 7 | 3 | 2026-04-24 |
| [[sources/02a1c3dc2ba1\|02a1c3dc2ba1]] | CO2_N2_separation | 7 | 4 | 2026-04-24 |
| [[sources/dc8e95b470bb\|Atz-PO4Angew Chem Int Ed - 2011 - Vaidhy]] | CO2_capture | 4 | 5 | 2026-04-24 |
| [[sources/3102127ab41f\|Adsorption of Iodine Based on a Tetrazol]] | gas_separation | 2 | 3 | 2026-04-24 |
| [[sources/8f5c2cf04665\|A three-dimensional metal–organic framew]] | gas_separation | 2 | 3 | 2026-04-24 |
| [[sources/819514b3add8\|Selective gas adsorption and fluorescenc]] | CO2_capture | 2 | 2 | 2026-04-24 |
| [[sources/bdcdbf619520\|bdcdbf619520]] | CO2_N2_separation | 4 | 7 | 2026-04-24 |
| [[sources/e5c646067ae0\|Control of intracrystalline diffusion in]] | C3H6_C3H8_separation | 1 | 2 | 2026-04-24 |
| [[sources/fc50783c6918\|Efficient carbon dioxide capture from fl]] | CO2_capture | 4 | 3 | 2026-04-24 |
| [[sources/6a5b1f4fd296\|6a5b1f4fd296]] | CO2_capture | 3 | 2 | 2026-04-24 |
| [[sources/32ff123187b3\|Carbon Dioxide Capture in a Carbonate-Pi]] | CO2_capture | 2 | 4 | 2026-04-24 |
| [[sources/c4b74fb8fd1c\|Pillared metal organic frameworks for th]] | gas_separation | 5 | 4 | 2026-04-24 |
| [[sources/4ac5d26e2f79\|4ac5d26e2f79]] | CO2_capture | 2 | 1 | 2026-04-24 |
| [[sources/4358ab539332\|4358ab539332]] | gas_separation | 1 | 0 | 2026-04-24 |
| [[sources/c7d06ee112e6\|The design of a novel and resistant Zn(P]] | CO2_capture | 1 | 5 | 2026-04-24 |
| [[sources/94f7b4957cbd\|94f7b4957cbd]] | CO2_capture | 4 | 3 | 2026-04-24 |
| [[sources/f06b5fb682b1\|f06b5fb682b1]] | CO2_capture | 16 | 4 | 2026-04-24 |
| [[sources/5490d74e9536\|Achieving Superprotonic Conduction in Me]] | gas_separation | 14 | 8 | 2026-04-24 |
| [[sources/5aa321e49dbe\|5aa321e49dbe]] | gas_separation | 8 | 4 | 2026-04-24 |
| [[sources/30d4205afd7a\|CO2N2 separation by vacuum swing adsorpt]] | CO2_capture | 1 | 5 | 2026-04-24 |
| [[sources/b33f5192881b\|Immobilization of H2O in Diffusion Chann]] | CO2_capture | 4 | 5 | 2026-04-24 |
| [[sources/c2ce30b6259c\|c2ce30b6259c]] | H2_storage | 7 | 4 | 2026-04-24 |
| [[sources/7eafab3ec2e2\|An amine-functionalized metal organic fr]] | CO2_capture | 3 | 3 | 2026-04-24 |
| [[sources/bcfc40db266f\|Adsorption of Iodine Based on a Tetrazol]] | gas_separation | 3 | 1 | 2026-04-24 |
| [[sources/ad4930c0a0d3\|Solvent-Induced Topological Variation in]] | C2H2_C2H4_separation | 2 | 3 | 2026-04-24 |
| [[sources/9c7fd9f72c5c\|9c7fd9f72c5c]] | CO2_capture | 6 | 4 | 2026-04-24 |
| [[sources/25907edd8ee8\|25907edd8ee8]] | CO2_N2_separation | 15 | 4 | 2026-04-24 |
| [[sources/8fe522d31fa4\|8fe522d31fa4]] | C2H2_CO2_separation | 15 | 7 | 2026-04-24 |
| [[sources/f849bda00a63\|Exceptionally Stable and Hollow Tubular ]] | gas_separation | 1 | 1 | 2026-04-24 |
| [[sources/57e1f73b209f\|57e1f73b209f]] | gas_separation | 2 | 3 | 2026-04-24 |
| [[sources/49b2ebb2b8e4\|49b2ebb2b8e4]] | gas_separation | 5 | 2 | 2026-04-24 |
| [[sources/318d01c9cf2b\|318d01c9cf2b]] | CO2_N2_separation | 1 | 3 | 2026-04-24 |
| [[sources/23e9ac5655c5\|23e9ac5655c5]] | gas_separation | 6 | 3 | 2026-04-24 |
| [[sources/09e67f192def\|Metal Azolate Frameworks From Crystal En]] | C2H2_CO2_separation | 64 | 0 | 2026-04-24 |
| [[sources/0d1cacffbd0b\|SCN-.OX.BTC-hai 等。 - 2007 - Coligand Mod]] | gas_separation | 7 | 4 | 2026-04-24 |
| [[sources/5b0277415f17\|5b0277415f17]] | CO2_capture | 6 | 3 | 2026-04-24 |
| [[sources/bc94c5cb3329\|bc94c5cb3329]] | CO2_N2_separation | 2 | 0 | 2026-04-24 |
| [[sources/de406c62e157\|BTEC水解]] | CO2_capture | 12 | 4 | 2026-04-24 |
| [[sources/cd232c378576\|Kinetic separation of propylene over pro]] | C3H6_C3H8_separation | 3 | 2 | 2026-04-24 |
| [[sources/a81a4cda2196\|Construction of a zeolite A-type multiva]] | gas_separation | 2 | 3 | 2026-04-24 |
| [[sources/c79105a7e122\|Studies on the removal of phosphate in w]] | gas_separation | 10 | 2 | 2026-04-24 |
| [[sources/13ab371bdaeb\|Structures, luminescence and magnetic pr]] | H2_storage | 2 | 3 | 2026-04-24 |
| [[sources/cd0fc62673f6\|Stitching 2D Polymeric Layers into Flexi]] | gas_separation | 20 | 5 | 2026-04-24 |
| [[sources/6613653bbccc\|6613653bbccc]] | gas_separation | 2 | 5 | 2026-04-24 |
| [[sources/6d91fe8710db\|Syntheses, structures, and photoluminesc]] | gas_separation | 6 | 6 | 2026-04-24 |
| [[sources/97fd14a47cac\|SO4-Angew Chem Int Ed - 2025 - Wang - Mu]] | CO2_capture | 8 | 3 | 2026-04-24 |
| [[sources/6514269e82d9\|6514269e82d9]] | gas_separation | 1 | 6 | 2026-04-24 |
| [[sources/0e0372bd7999\|Engineering the Microporous Environment ]] | C2H2_C2H4_separation | 4 | 4 | 2026-04-24 |
| [[sources/6b0b28490990\|6b0b28490990]] | CO2_capture | 1 | 2 | 2026-04-24 |
| [[sources/a8e30ce28b53\|a8e30ce28b53]] | CO2_capture | 2 | 3 | 2026-04-24 |
| [[sources/9a4d07d3bef9\|9a4d07d3bef9]] | CO2_capture | 4 | 2 | 2026-04-24 |
| [[sources/bc92a6860fda\|A scalable ultramicroporous metal-organi]] | C3H6_C3H8_separation | 2 | 3 | 2026-04-24 |
| [[sources/b693b8f886ee\|Effect of Fluorination on the Crystal St]] | C2H2_CO2_separation | 4 | 3 | 2026-04-24 |
| [[sources/40538d8f41b8\|40538d8f41b8]] | gas_separation | 1 | 3 | 2026-04-24 |
| [[sources/915a83b12e95\|Selective adsorption and separation of C]] | C2H2_C2H4_separation | 1 | 5 | 2026-04-24 |
| [[sources/e491473623b9\|Fine-Tuning MOFs with Amino Group for On]] | C2H2_C2H4_separation | 7 | 4 | 2026-04-24 |
| [[sources/09be42eaae90\|09be42eaae90]] | C2H2_C2H4_separation | 2 | 4 | 2026-04-24 |
| [[sources/a440f91e7e1a\|Restoring Porosity and Uncovering Flexib]] | CO2_capture | 6 | 4 | 2026-04-24 |
| [[sources/03636bfd549e\|03636bfd549e]] | gas_separation | 11 | 7 | 2026-04-24 |
| [[sources/2c4071961196\|2c4071961196]] | gas_separation | 5 | 0 | 2026-04-24 |
| [[sources/7b72d2604f90\|Zn Metal–Organic Framework with High Sta]] | CO2_capture | 1 | 1 | 2026-04-24 |
| [[sources/4138e79cf7f6\|4138e79cf7f6]] | C2H2_C2H4_separation | 1 | 5 | 2026-04-24 |
| [[sources/6d0b831e801b\|Four Zn(II)Cd(II)-3-amino-1,2,4-triazola]] | gas_separation | 3 | 5 | 2026-04-24 |
| [[sources/3e1294c811a4\|3e1294c811a4]] | C2H2_CO2_separation | 3 | 3 | 2026-04-24 |
| [[sources/3acf5b3581ba\|A three-dimensional metal–organic framew]] | gas_separation | 2 | 4 | 2026-04-24 |
| [[sources/e0c6d76c92fc\|Programmed Pore Engineering in an Isoret]] | C2H2_C2H4_separation | 4 | 4 | 2026-04-24 |
| [[sources/63f0d3e9e0fb\|High CO 2 and H 2 Uptake in]] | CO2_capture | 2 | 0 | 2026-04-24 |
| [[sources/8a5789906247\|8a5789906247]] | CO2_capture | 1 | 2 | 2026-04-24 |
| [[sources/6f8496567c7f\|A Zn(II) Pillared-Layer Ultramicroporous]] | C2H2_CO2_separation | 1 | 3 | 2026-04-24 |
| [[sources/b995768c76e0\|CO3-Angew Chem Int Ed - 2024 - Zhao - Ex]] | CO2_capture | 3 | 4 | 2026-04-24 |
| [[sources/5e115f0ab554\|Pillar-layer Zn–triazolate–dicarboxylate]] | C2H2_C2H4_separation | 1 | 3 | 2026-04-24 |
| [[sources/ffba90254f37\|ffba90254f37]] | gas_separation | 8 | 6 | 2026-04-24 |
| [[sources/c5a7573ead67\|c5a7573ead67]] | C2H2_CO2_separation | 1 | 1 | 2026-04-24 |
| [[sources/14d4b8abc8fc\|14d4b8abc8fc]] | C2H2_C2H4_separation | 1 | 5 | 2026-04-24 |
| [[sources/537a8fa3b41c\|537a8fa3b41c]] | gas_separation | 3 | 2 | 2026-04-24 |
| [[sources/fbf7094ee3a4\|Competitive CO2H2O Adsorption on CALF-20]] | CO2_capture | 5 | 7 | 2026-04-24 |
| [[sources/03314ed46af4\|Achieving Superprotonic Conduction in Me]] | gas_separation | 9 | 0 | 2026-04-24 |
| [[sources/70cdcc23a105\|One-step ethylene purification from tern]] | C2H2_C2H4_separation | 1 | 1 | 2026-04-24 |
| [[sources/5ec53d505118\|Role of molar-ratio, temperature and sol]] | gas_separation | 7 | 4 | 2026-04-24 |
| [[sources/3c82aca435dd\|SO4-Applied Organom Chemis - 2017 - Ren ]] | gas_separation | 3 | 4 | 2026-04-24 |
| [[sources/437971f0d489\|437971f0d489]] | CO2_capture | 3 | 4 | 2026-04-24 |
| [[sources/1ea61295e3c3\|1ea61295e3c3]] | C2H2_C2H4_separation | 5 | 7 | 2026-04-24 |
| [[sources/beb388971362\|beb388971362]] | CO2_capture | 16 | 4 | 2026-04-24 |
| [[sources/331085fe34df\|331085fe34df]] | C2H2_C2H4_separation | 8 | 8 | 2026-04-24 |
| [[sources/5250c7918a49\|5250c7918a49]] | gas_separation | 10 | 1 | 2026-04-24 |
| [[sources/7ea1666a932f\|Synthesis, Structures, and Luminescent P]] | gas_separation | 3 | 3 | 2026-04-24 |
| [[sources/93a072e837ab\|Stitching 2D Polymeric Layers into Flexi]] | gas_separation | 15 | 4 | 2026-04-24 |
| [[sources/b3e6c07b82b5\|b3e6c07b82b5]] | gas_separation | 2 | 1 | 2026-04-24 |
| [[sources/08078d819c99\|Two Unprecedented 3-Connected Three-Dime]] | gas_separation | 3 | 3 | 2026-04-24 |
| [[sources/24731d45e39f\|Synthesis, crystal structures and proper]] | gas_separation | 4 | 3 | 2026-04-24 |
| [[sources/20a73d2f96f4\|Exhaled Anesthetic Xenon Regeneration by]] | CO2_capture | 3 | 3 | 2026-04-24 |
| [[sources/7d1015d4b98c\|SO4-anion-controlled-assembly-of-a-silve]] | gas_separation | 6 | 3 | 2026-04-24 |
| [[sources/2402f4b4cedf\|Hydrothermal Synthesis and Structural Ch]] | gas_separation | 6 | 7 | 2026-04-24 |
| [[sources/943305fdca28\|SO4-hydrothermal-and-structural-chemistr]] | gas_separation | 8 | 5 | 2026-04-24 |
| [[sources/183091a2e8c1\|183091a2e8c1]] | C2H2_C2H4_separation | 7 | 4 | 2026-04-24 |
| [[sources/a2bbb951fd66\|a2bbb951fd66]] | CO2_capture | 1 | 2 | 2026-04-24 |
| [[sources/2ff55e6ee723\|Solvothermal Synthesis, Crystal Structur]] | gas_separation | 1 | 0 | 2026-04-24 |
| [[sources/c200d37114d8\|c200d37114d8]] | gas_separation | 5 | 2 | 2026-04-24 |
| [[sources/8447b81d8a48\|8447b81d8a48]] | gas_separation | 6 | 3 | 2026-04-24 |
| [[sources/54f9fbaf30b0\|54f9fbaf30b0]] | gas_separation | 1 | 0 | 2026-04-24 |
| [[sources/ed2e02bdfbe8\|ed2e02bdfbe8]] | CO2_capture | 6 | 7 | 2026-04-24 |
| [[sources/d67c409db37b\|d67c409db37b]] | C2H2_C2H4_separation | 1 | 4 | 2026-04-24 |
| [[sources/6dce67f7e059\|Sensitive luminescent probes of aniline,]] | gas_separation | 3 | 2 | 2026-04-24 |
| [[sources/61c7ed14218a\|The design of a novel and resistant Zn(P]] | CO2_capture | 1 | 4 | 2026-04-24 |
| [[sources/125eb726c7ef\|A porous anionic zinc(II) metal–organic ]] | CO2_capture | 3 | 1 | 2026-04-24 |
| [[sources/d17e8bdce2c0\|Electronic Supplementary Information (ES]] | C2H2_C2H4_separation | 1 | 1 | 2026-04-24 |
| [[sources/f3cdab115144\|f3cdab115144]] | CO2_N2_separation | 1 | 2 | 2026-04-24 |
| [[sources/a4f10cb0fd34\|Selective gas adsorption and fluorescenc]] | CO2_capture | 2 | 3 | 2026-04-24 |
| [[sources/d9d19a39346c\|d9d19a39346c]] | gas_separation | 4 | 5 | 2026-04-24 |
| [[sources/62abef84986f\|62abef84986f]] | CO2_capture | 15 | 7 | 2026-04-24 |
| [[sources/bb5e40031d43\|3D Pillar-Layered Zn(II) Compound with 6]] | gas_separation | 2 | 0 | 2026-04-24 |
| [[sources/ca3213a92d15\|ca3213a92d15]] | C2H2_CO2_separation | 2 | 4 | 2026-04-24 |
| [[sources/ee80b65b2eff\|A Flexible Porous MOF Exhibiting Reversi]] | gas_separation | 4 | 1 | 2026-04-24 |
| [[sources/a75f77b10e12\|a75f77b10e12]] | CO2_N2_separation | 1 | 4 | 2026-04-24 |
| [[sources/fc15206cdae2\|Two Novel Zinc(II) Metal–Organic Framewo]] | CO2_N2_separation | 1 | 2 | 2026-04-24 |
| [[sources/e050ac390c87\|e050ac390c87]] | CO2_N2_separation | 5 | 4 | 2026-04-24 |
| [[sources/2618bcaf2994\|Rapid Cycle Temperature Swing Adsorption]] | CO2_capture | 1 | 1 | 2026-04-24 |
| [[sources/cb0db3cfb790\|cb0db3cfb790]] | CO2_capture | 16 | 5 | 2026-04-24 |
| [[sources/1e03e8a24ac5\|Synthesis, crystal structures and proper]] | gas_separation | 6 | 4 | 2026-04-24 |
| [[sources/64afdaef56aa\|64afdaef56aa]] | gas_separation | 1 | 4 | 2026-04-24 |
| [[sources/8cb3c4f4e106\|Facile synthesis and superior properties]] | gas_separation | 2 | 4 | 2026-04-24 |
| [[sources/853299a980a3\|853299a980a3]] | CO2_N2_separation | 2 | 3 | 2026-04-24 |
| [[sources/ddc984c6572e\|Framework isomers controlled by the spee]] | CO2_capture | 0 | 3 | 2026-04-24 |
| [[sources/a73000c53af6\|a73000c53af6]] | gas_separation | 1 | 2 | 2026-04-24 |
| [[sources/b2c6560d9efc\|HPO4-aitenneite2012-Poly[(l3-hydrogenpho]] | gas_separation | 1 | 0 | 2026-04-24 |
| [[sources/9daa86d6b3c0\|9daa86d6b3c0]] | gas_separation | 3 | 4 | 2026-04-24 |
| [[sources/dc6fb3fab588\|dc6fb3fab588]] | gas_separation | 4 | 0 | 2026-04-28 |
| [[sources/8fece016b962\|8fece016b962]] | gas_separation | 7 | 1 | 2026-04-28 |
| [[sources/7d76885b5ec5\|7d76885b5ec5]] | C2H2_CO2_separation | 3 | 5 | 2026-04-28 |
| [[sources/ee6e24a30498\|ee6e24a30498]] | C2H2_CO2_separation | 4 | 3 | 2026-04-28 |
| [[sources/287429d86099\|287429d86099]] | gas_separation | 1 | 0 | 2026-04-28 |
| [[sources/6719a09a449d\|6719a09a449d]] | CO2_capture | 1 | 2 | 2026-04-28 |
| [[sources/b5d313a80058\|b5d313a80058]] | gas_separation | 1 | 0 | 2026-04-28 |
| [[sources/1b118e60d7ac\|1b118e60d7ac]] | gas_separation | 1 | 1 | 2026-04-28 |
| [[sources/a4c5917133a0\|a4c5917133a0]] | gas_separation | 2 | 0 | 2026-04-28 |
| [[sources/9a3286216110\|9a3286216110]] | gas_separation | 2 | 0 | 2026-04-28 |
| [[sources/b002da0f0c54\|b002da0f0c54]] | gas_separation | 0 | 0 | 2026-04-28 |
| [[sources/5bd6d1cae658\|5bd6d1cae658]] | C2H2_C2H4_separation | 2 | 0 | 2026-04-28 |
| [[sources/d7d931748afa\|d7d931748afa]] | gas_separation | 0 | 0 | 2026-04-28 |
| [[sources/0ed2013c63d4\|0ed2013c63d4]] | CO2_N2_separation | 2 | 3 | 2026-04-28 |
| [[sources/99cce61e0b82\|99cce61e0b82]] | C3H6_C3H8_separation | 3 | 0 | 2026-04-28 |
| [[sources/3b10485188f4\|3b10485188f4]] | gas_separation | 2 | 0 | 2026-04-28 |
| [[sources/07583595bdf7\|07583595bdf7]] | C2H2_C2H4_separation | 1 | 1 | 2026-04-28 |
| [[sources/94e80a9c0ffd\|94e80a9c0ffd]] | gas_separation | 12 | 2 | 2026-04-28 |
| [[sources/76162d2dc290\|76162d2dc290]] | CO2_capture | 5 | 1 | 2026-04-28 |
| [[sources/7053ffe8885e\|7053ffe8885e]] | gas_separation | 2 | 1 | 2026-04-28 |
| [[sources/8bcfad0f6e91\|8bcfad0f6e91]] | gas_separation | 1 | 2 | 2026-04-28 |
| [[sources/3f432af49e67\|3f432af49e67]] | C3H6_C3H8_separation | 2 | 3 | 2026-04-28 |

---

## 相关页面

- [[log.md]] — 操作日志
