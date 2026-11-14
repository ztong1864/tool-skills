# 默认文献索引（aerobic oxidation）

这是 `literature-experiment-recommender` 自带的默认文献，**只在本次任务没有自带 PDF 时使用**
（`write_recommendations.py --literature-status` 的 `mode` 为 `default_literature`）。
任务自带 PDF 时以那些为准，这里的内容不要混进去。

**先读这张表，挑最接近本次反应的 2–3 篇再读全文，不要把 23 篇都读一遍。**

## 这批文献覆盖什么

23 篇，全部是**好氧氧化（aerobic oxidation）**：以 O2 或空气为氧化剂，
Fe(NO3)3·9H2O / TEMPO / NaCl（部分用 4-OH-TEMPO、KCl，或改用铜盐）催化，多为室温常压。
底物覆盖醇（一级、二级、苄基、烯丙、炔丙、高炔丙）、醛、二醇、PMB 醚、硅醚、isochroman、吲哚甲醇；
产物覆盖醛/酮、羧酸、酯和**内酯（氧化内酯化）**。

**不覆盖**：端炔与醛的联烯化（ATA）、手性胺/金属盐促进的不对称加成、偶联反应、光催化。
本次反应明显不在上面的范围内时，按实际情况说明文献依据有限，不要把这些条件硬套过去。

## 篇目

| # | 文件 | 催化体系 | 反应与用途 |
|---|---|---|---|
| 1 | `01-iron-nitrate-tempo-nacl-general-method.md` | Fe(NO3)3·9H2O / TEMPO / NaCl, O2, r.t. | 醇 → 醛/酮。本催化体系的通用方法原文；查载量和溶剂筛选先看这篇。 |
| 2 | `02-propargyl-alcohol-to-propiolaldehyde.md` | Fe(NO3)3·9H2O (5 mol%) / TEMPO (3 mol%) / NaCl (5 mol%), p-xylene, O2, r.t. | 炔丙醇 → 丙炔醛。摩尔级的完整实验步骤，含后处理与蒸馏。 |
| 3 | `03-allylic-alcohols-cc-isomerization.md` | Fe(NO3)3·9H2O / TEMPO / NaCl, O2 | 烯丙醇 → 烯醛/烯酮，以及 C=C 何时发生迁移。看选择性边界用这篇。 |
| 4 | `04-homopropargylic-alcohols.md` | Fe(NO3)3·9H2O (10 mol%) / TEMPO (10 mol%) / NaCl (10 mol%), O2, r.t. | 高炔丙醇 → 相应羰基化合物。带溶剂筛选表。 |
| 5 | `05-alcohols-to-carboxylic-acids-iron.md` | Fe(NO3)3·9H2O (10 mol%) / TEMPO (10 mol%) / KCl (10 mol%), DCE, O2 or air, r.t. | 醇 → 羧酸（有意过氧化）。注意用的是 KCl 而不是 NaCl。 |
| 6 | `06-lamenallenic-acid-allene-synthesis.md` | Fe(NO3)3·9H2O / TEMPO / NaCl aerobic oxidation, within a multi-step allene synthesis | 多步手性联烯（联烯酸）合成里的好氧氧化那一步。本批中与联烯化学最接近的一篇。 |
| 7 | `07-aldehydes-single-component-mechanism.md` | iron nitrate, single-component, O2 | 醛 → 羧酸，并讨论机理。想知道体系里每个组分各做什么，看这篇。 |
| 8 | `08-benzylic-alcohols-to-acids.md` | Fe(NO3)3·9H2O / TEMPO / chloride, O2 | 苄醇 → 羧酸，附条件考察。 |
| 9 | `09-benzopyranones-one-pot-cyclization.md` | Fe(NO3)3·9H2O / TEMPO / NaCl, then DMAP, O2 | 一锅法先氧化再环化得黄酮。氧化之后再接一步催化反应的例子。 |
| 10 | `10-lower-cost-4-oh-tempo-selectivity.md` | Fe(NO3)3·9H2O / 4-OH-TEMPO / NaCl, O2 | 醇 → 醛/酮，改用更便宜的 4-OH-TEMPO。以成本或选择性为约束时看这篇。 |
| 11 | `11-copper-selective-alcohols-to-carbonyls.md` | copper salt / TEMPO, O2 | 醇 → 醛/酮，改用铜盐而非铁盐。换金属的备选路线。 |
| 12 | `12-isochromans-4-oh-tempo.md` | Fe(NO3)3 / 4-OH-TEMPO, O2 | isochroman → 内酯。与氧化内酯化相关。 |
| 13 | `13-copper-primary-alcohols-to-acids.md` | copper salt / TEMPO, O2 | 一级醇 → 羧酸，铜催化。 |
| 14 | `14-iron-14-diols.md` | Fe(NO3)3·9H2O / TEMPO / NaCl, O2 | 1,4-二醇 → 内酯。二醇的氧化内酯化。 |
| 15-SI | `15-SI-oxidative-esterification-with-methanol-SI.md` | relay catalysis, O2, methanol as the nucleophile | 一级醇 + 甲醇 → 甲酯。**本批里只有它的 Supporting Information，没有正文**；SI 本身是全文转换，实验步骤和表征数据都在。 |
| 16 | `16-silyl-ethers-to-acids.md` | Fe(NO3)3·9H2O / TEMPO / NaCl, O2 | 硅醚 → 羧酸，直接越过保护基氧化。 |
| 17 | `17-pmb-ethers-to-acids.md` | iron nitrate / TEMPO, O2 | PMB 醚 → 羧酸。官能团互换。 |
| 18 | `18-propargylic-alcohols-to-alkynals-toluene.md` | Fe(NO3)3·9H2O / TEMPO / NaCl, toluene, O2 | 炔丙醇 → 炔醛/炔酮，溶剂为甲苯。可与第 2 篇的对二甲苯条件对照。 |
| 19 | `19-pmb-ethers-to-carbonyls.md` | iron nitrate / TEMPO, O2 | PMB 醚 → 醛/酮，停在酸之前。 |
| 20 | `20-copper-aldehydes-to-acids.md` | Cu salt / TEMPO, O2 | 醛 → 羧酸，铜催化。 |
| 21 | `21-dual-iron-lactonization-16-diols.md` | dual iron catalysis, O2 | 1,6-二醇 → 己内酯，并可进一步到聚己内酯。**本批里的氧化内酯化代表作。** |
| 22 | `22-copper-nitrate-mechanism-acids.md` | Cu(NO3)2 / TEMPO, O2 | 铜路线到羧酸的机理研究。 |
| 23 | `23-indole-carbinols.md` | Fe(NO3)3·9H2O / TEMPO / NaCl, O2 | 吲哚甲醇 → 相应羰基化合物。一个能耐受该体系的杂芳底物。 |

## 来源与转换

原始 PDF 来自平台账号 `xmart_55` 上传的 `aerobic oxidation` 目录（23 个文件，44 MB），
用 **MinerU 云端精读接口**（`/api/v4`，`pipeline` 模型，开启公式与表格识别）转成 Markdown：
正文、实验步骤和条件筛选表格（HTML `<table>`）都保留，公式转成 LaTeX，图片只留 `<!-- image -->` 占位。
**23 篇都是全文转换，没有按页截断。** 文件名里的编号对应原始 PDF 的文件名（`1.pdf` → `01-...`）。

一点要知道：`15-SI` 这一篇本批里只有 Supporting Information，没有正文——是上传目录里本来就没有，
不是转换丢的。引用它时说明依据来自 SI。

需要重做或新增时重新跑一次转换脚本，并同步更新这张表。
