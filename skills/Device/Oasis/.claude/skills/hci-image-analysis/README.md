# HCI 图像分析 Skill+CLI 交接说明

这个交接包用于把 W1/W2 高内涵显微图像转换为可复核的细胞核、细胞质和 W2 强度指标，并与 MetaXpress `MultiWaveScoring` 软件结果对比。

第一版支持当前数据结构：96 孔板、每孔 4 个 site、`w1 = nucleus`、`w2 = marker/cytoplasm`。B/C 可作为对照/模型参照组，D-G 等给药孔也会被保留；真实筛药场景建议提供 position map 或 plate map 来说明药物位置。

## 1. 输入图像格式

图像文件按 `实验名_孔位_s视野_w通道*.tif` 解析。典型示例：

```text
0513-2_B02_s1_w1xxxx.tif
0513-2_B02_s1_w2xxxx.tif
0602-7-1-1_B02_s1_w1xxxx.tif
0602-7-1-1_B02_s1_w2xxxx.tif
```

字段含义：

| 字段 | 示例 | 含义 |
|---|---|---|
| `实验名` | `0513-2`、`0602-7-1-1` | 同一批图像或同一块板的实验/板编号 |
| `孔位` | `B02` | 96 孔板坐标，行号 A-H、列号 01-12 |
| `s视野` | `s1`-`s4` | 同一孔的不同视野，当前默认每孔 4 个视野 |
| `w通道` | `w1` / `w2` | `w1` 为核通道，`w2` 为 BODIPY/Marker/细胞质通道 |
| `_thumb` | `*_thumb*.tif` | 缩略图，`prepare` 默认跳过，不进入分析 |

通道解释：

- `w1`：蓝色核通道，例如 Hoechst/DAPI，用于核分割、核计数和细胞数估计。
- `w2`：绿色 BODIPY/Marker/细胞质通道，用于计算 W2 强度。

`prepare` 会递归扫描 `--image-root` 下的 `.tif`，自动配对同一 `experiment + well + site` 的 `w1/w2`，并输出 `manifest.csv`。同时会生成 CellProfiler 可直接读取的 `cp_loaddata.csv`。manifest 至少包含：

| 字段 | 含义 |
|---|---|
| `experiment` | 从文件名中孔位前的部分解析得到，例如 `0513-2` |
| `acquisition` | 从目录层级推断的采集批次/板目录名 |
| `well` | 孔位，例如 `B02` |
| `site` | 视野编号，例如 `1` |
| `group` | 按 `--group-mode` 或 position map 生成的分组标签 |
| `nucleus_path` | w1 核通道图像路径 |
| `marker_path` | w2 marker/细胞质通道图像路径 |
| 其他列 | position map 中提供的药物、剂量、重复、处理编号等字段会原样保留 |

如果文件名不符合 `实验名_孔位_s视野_w通道`，需要先提供文件名样例或 position map/plate map，再扩展 `prepare` 的解析规则。

## 2. 孔板布局与分组

默认分析 96 孔板内圈 `B-G` 行、`02-11` 列。分组不写死在算法里，应由 `prepare --group-mode` 或 plate map 决定。当前内置两种常用规则：

| `--group-mode` | 分组规则 | 适用场景 |
|---|---|---|
| `bc` | `B = control`，`C = model`，`D-G = treat` | 0609 / Positive W2 软件复现实验 |
| `bodipy0513` | `B02-B11 = BSA`，`C02-C11 = FM`，`D-G = drug` | BODIPY 0513 报告逻辑 |
| `none` | 不自动分组 | 需要外部 plate map 的新实验 |

示例：

```bash
python hci_image_analysis_skill/scripts/hci_hcs.py prepare \
  --image-root /path/to/BODIPY_0513 \
  --group-mode bodipy0513 \
  --out outputs/bodipy_0513
```

### 2.1 Position Map / Plate Map

真实给药筛选时，输入可能只有“药物在哪些孔”，不一定有完整剂量和重复信息。因此 `prepare` 支持可选的 position map，也可称为 plate map。这个文件可以是 `.csv`、`.tsv`、`.xlsx`，最低要求只有一列：

```csv
well
D02
D03
E02
```

更常用的轻量格式是：

```csv
well,compound
D02,drug_A
D03,drug_A
E02,drug_B
```

如果实验记录更完整，也可以提供：

```csv
well,group,compound,dose,dose_unit,replicate
B02,control,NA,NA,NA,1
C02,model,NA,NA,NA,1
D02,treat,drug_A,10,uM,1
D03,treat,drug_A,10,uM,2
E02,treat,drug_B,5,uM,1
```

规则：

- 只要有 `well`/`孔位` 列即可合并；其他列有就保留，没有就留空。
- 如果 position map 里有 `group`，优先使用它；否则用 `--group-mode` 作为兜底。
- 如果有 `acquisition` 列，则按 `acquisition + well` 精确匹配；如果没有，则同一个孔位规则会应用到所有 acquisition。
- 程序不会根据孔位猜药物名、剂量或重复编号。
- 0609 这类目录名 `0609 1-1 15-2` 会额外解析为 `date_batch=0609`、`plate_repeat=1-1`、`treatment_set=15-2`，用于和实验记录对应。

示例：

```bash
python hci_image_analysis_skill/scripts/hci_hcs.py prepare \
  --image-root /path/to/images \
  --position-map drug_positions.csv \
  --group-mode bc \
  --out outputs/run_x
```

## 3. 单视野与单孔计算规则

单视野层面：

| 指标 | 计算方式 |
|---|---|
| `cell_count` | w1 核分割得到的核数 |
| `total_integr` | w2 在有效细胞质区域内的积分强度；BODIPY 场景可理解为背景扣除或原始绿光总强度 |
| `mean_integr` | CellProfiler object-level 平均，或简化 BODIPY 逻辑中的 `total_integr / cell_count` |
| `total_area` | 有效细胞质区域总面积 |
| `per_area` | `total_integr / total_area` |

单孔层面：

- 同一孔 4 个视野取平均，得到 `per_well_metrics.csv`。
- 若某视野核数为 0 或没有有效对象，该视野默认不参与孔均值。
- `site_cv` 是同孔 4 个视野 `mean_integr` 的变异系数，用于标记高波动孔。
- `site_cv > 0.5` 只能称为高 site 波动，不能直接等同于模糊图。

0609 的软件复现主要看 `Positive W2 Mean Cyto Integr Intens`、C/B、raw/log/Spearman 相关。BODIPY 0513 的报告逻辑主要看 `green/cell` 和 `normalized_to_bsa`，二者是同类 W1/W2 高内涵流程，但归一化和判读方向不同，不能混写。

## 4. 三种方法的定位

| backend | 定位 | 适合场景 |
|---|---|---|
| `cellprofiler` | 默认生产流程 | 批量跑板、输出 object 表、复现软件 Positive W2 |
| `skimage` | 轻量开源复核 | 快速检查、输出 `per_area`、验证成团孔 |
| `cellpose` | 深度学习复核 | 争议孔、成团孔、核分割对照；不默认全板跑 |

## 5. 环境

建议计算机团队使用独立 conda 环境，不依赖交接方本机路径。下面是推荐方式，环境名可按团队习惯调整。

基础分析环境用于 pandas、numpy、scipy、scikit-image、tifffile：

```bash
conda create -n hci-analysis python=3.10 pandas numpy scipy scikit-image tifffile openpyxl -y
conda activate hci-analysis
python hci_image_analysis_skill/scripts/hci_hcs.py --help
```

CellProfiler 是推荐的生产路线，但不是必须安装。如果团队希望复现软件 Positive W2 的对象级流程，建议独立安装 CellProfiler；如果暂时不安装，可以先使用 `skimage` 路线，并在报告中明确标注 backend 为 `skimage`。

推荐用 Bioconda 新建独立 CellProfiler 环境，不要装进 base：

```bash
conda create -n cellprofiler -c conda-forge -c bioconda cellprofiler -y
conda activate cellprofiler
cellprofiler --version
```

如果 `cellprofiler --version` 能输出版本号，说明命令行环境基本可用。然后可以直接运行 skill 的默认 CellProfiler 流程，通常不需要额外传 `.cppipe`，因为 skill 已内置 `assets/cellprofiler/default_positive_w2.cppipe`：

```bash
python hci_image_analysis_skill/scripts/hci_hcs.py run \
  --backend cellprofiler \
  --manifest outputs/run_x/manifest.csv \
  --out outputs/run_x/cellprofiler
```

如果团队已经安装了 CellProfiler 桌面版，但命令行里没有 `cellprofiler`，运行时用 `--cellprofiler-bin` 指定实际可执行文件。例如 macOS 桌面版可能是：

```bash
python hci_image_analysis_skill/scripts/hci_hcs.py run \
  --backend cellprofiler \
  --manifest outputs/run_x/manifest.csv \
  --cellprofiler-bin /Applications/CellProfiler.app/Contents/MacOS/cp \
  --out outputs/run_x/cellprofiler
```

如果安装失败，优先把完整报错保留下来；常见问题来自 Java、wxPython 或 CellProfiler 依赖包版本冲突。不要为了修 CellProfiler 去升级 `hci-analysis` 基础环境里的 `numpy/scipy`。安装暂时不可用时，可以继续跑 `skimage`，但结论中应写清楚这是 skimage 结果，不是 CellProfiler 默认流程结果。

cellpose 也建议独立环境，避免和 scikit-image/CellProfiler 的依赖冲突。注意：本 skill 的 CLI 入口需要 `pandas`，所以 cellpose 环境不能只装 cellpose 本体，还要包含 pandas、scikit-image、scipy、tifffile 等基础包。

推荐新建环境：

```bash
conda create -n cellpose python=3.10 pandas scipy scikit-image tifffile -y
conda activate cellpose
python -m pip install cellpose
python - <<'PY'
import pandas, cellpose, skimage, tifffile
print('cellpose environment OK')
PY
```

如果已有 cellpose 环境，但运行 skill 报 `No module named pandas`，补装即可：

```bash
conda activate cellpose
conda install pandas scipy scikit-image tifffile -y
```

运行 cellpose backend：

```bash
conda activate cellpose
python hci_image_analysis_skill/scripts/hci_hcs.py run --backend cellpose ...
```

默认使用 CPU，适合少量争议孔复核。如果团队确认 GPU/MPS 可用，可临时打开：

```bash
HCI_CELLPOSE_GPU=1 python hci_image_analysis_skill/scripts/hci_hcs.py run --backend cellpose ...
```

本地测试记录：补装 `pandas` 后，cellpose 环境可以同时导入 `pandas/cellpose/skimage/tifffile`，并能进入真实 B02 图像的 cellpose 模型推理阶段；但 CPU 下单孔 4 个视野运行超过 3 分钟，速度明显慢。因此 cellpose 在第一版交接中定位为“争议孔/成团孔复核”，不作为全板默认流程。

不要为了安装 cellpose 或 CellProfiler 直接升级基础分析环境里的 numpy/scipy；如需升级，先新建环境测试。

## 6. 标准运行命令

生成 manifest：

```bash
python hci_image_analysis_skill/scripts/hci_hcs.py prepare \
  --image-root /path/to/images \
  --group-mode bc \
  --out outputs/run_x
```

如果有药物位置表：

```bash
python hci_image_analysis_skill/scripts/hci_hcs.py prepare \
  --image-root /path/to/images \
  --position-map drug_positions.csv \
  --group-mode bc \
  --out outputs/run_x
```

运行 skimage：

```bash
python hci_image_analysis_skill/scripts/hci_hcs.py run \
  --backend skimage \
  --manifest outputs/run_x/manifest.csv \
  --out outputs/run_x/skimage
```

运行 cellpose 子集：

```bash
conda activate cellpose
python hci_image_analysis_skill/scripts/hci_hcs.py run \
  --backend cellpose \
  --manifest outputs/run_x/manifest.csv \
  --wells B02,C02,D04 \
  --out outputs/run_x/cellpose
```

运行 CellProfiler（默认使用内置 pipeline）：

```bash
python hci_image_analysis_skill/scripts/hci_hcs.py run \
  --backend cellprofiler \
  --manifest outputs/run_x/manifest.csv \
  --out outputs/run_x/cellprofiler
```

如果需要使用团队自己调整过的 `.cppipe`，再显式传入 `--pipeline`：

```bash
python hci_image_analysis_skill/scripts/hci_hcs.py run \
  --backend cellprofiler \
  --manifest outputs/run_x/manifest.csv \
  --pipeline /path/to/custom.cppipe \
  --out outputs/run_x/cellprofiler
```

对已有 CellProfiler 输出计分：

```bash
python hci_image_analysis_skill/scripts/hci_hcs.py score \
  --backend cellprofiler \
  --input outputs/run_x/cellprofiler \
  --manifest outputs/run_x/manifest.csv \
  --out outputs/run_x
```

对比三种 backend：

```bash
python hci_image_analysis_skill/scripts/hci_hcs.py compare-backends \
  --inputs outputs/run_x/cellprofiler outputs/run_x/skimage outputs/run_x/cellpose \
  --out outputs/run_x
```

与软件 Excel 对比：

```bash
python hci_image_analysis_skill/scripts/hci_hcs.py compare-software \
  --scores outputs/run_x/per_well_metrics.csv \
  --software-root /path/to/software_excels \
  --out outputs/run_x
```

生成 QC 表：

```bash
python hci_image_analysis_skill/scripts/hci_hcs.py qc-report \
  --scores outputs/run_x/per_well_metrics.csv \
  --out outputs/run_x/qc
```

## 7. 默认指标

默认主读数：

- `calibrated_integr_p95_1p25`
- `calibrated_integr_p95_1p30`

它们的计算基础是每孔 Cytoplasm object 的 W2 integrated intensity 第 95 百分位：

```text
integr_raw = Intensity_IntegratedIntensity_Marker * Scaling_Marker
integr_p95 = quantile(integr_raw, 0.95)
calibrated_integr_p95_1p25 = integr_p95 ^ 1.25
calibrated_integr_p95_1p30 = integr_p95 ^ 1.30
```

这两个指标是“软件复现/校准型指标”，不能写成完全独立的原始生物学指标。

保留的可选指标：

- `integr_p95`：独立 CellProfiler object-tail 指标。
- `top50_integr_mean`：早期 positive-object baseline。
- `per_area`：`total_integr / total_area`，不依赖细胞计数，适合成团孔复核。

注意：CellProfiler 只有在 pipeline 导出 `AreaShape_Area` 时才能计算 `per_area`。如果只跑了 intensity-only intermediate pipeline，CP 的 `per_area` 会是空值；此时应使用带 `MeasureObjectSizeShape` 的 CP pipeline，或使用 skimage/cellpose backend 复核 `per_area`。

## 8. 当前 0609 验证结果

| 方法 | raw Pearson | log10 Pearson | Spearman | CP C/B | 软件 C/B | 用途 |
|---|---:|---:|---:|---:|---:|---|
| `top50_integr_mean` | 0.806 | 0.958 | 0.890 | 5.16x | 8.22x | baseline |
| `integr_p95` | 0.826 | 0.951 | 0.881 | 5.27x | 8.22x | 独立 object 指标 |
| `integr_p95 + site_cv<=0.5` | 0.835 | 0.954 | 0.876 | 5.17x | 8.16x | 独立 raw Pearson 较高 |
| `integr_p95^1.25/1.30` | 0.853-0.855 | 0.954 | 0.876 | 7.9-8.6x | 8.16x | 默认校准型主指标 |
| `per_area` | 不主打软件复现 | 稳健 | 稳健 | 稳健 | 稳健 | 成团孔/计数不稳复核 |

## 9. QC 解释

- `site_cv > 0.5`：高 site 波动孔，需要标记；不能直接等同于模糊图。
- `missing_site`：缺少视野。
- `measured_ratio` 低：识别到细胞核但有效细胞质对象少。
- `large_object_count` 或面积 p99 高：可能存在成团或粘连对象。
- `module_error`：CellProfiler 模块运行异常。

## 10. 输出文件

| 文件 | 内容 |
|---|---|
| `manifest.csv` | 图像路径、well、site、w1/w2 通道；如提供 position map，也保留 compound/dose/replicate 等列 |
| `cp_loaddata.csv` | CellProfiler LoadData 输入表，由 `prepare` 自动生成 |
| `per_site_metrics.csv` | 每个 site 的统一指标 |
| `per_well_metrics.csv` | 每个孔汇总指标 |
| `object_metrics.csv` | object-level 指标，CellProfiler/skimage/cellpose 均可输出 |
| `backend_comparison.csv` | backend 之间的指标对照 |
| `software_comparison_summary.csv` | 与软件 Excel 的相关性和 C/B 对比 |
| `qc_flags.csv` | 需要人工复核的孔 |



## 11. 内置 CellProfiler Pipeline

默认 pipeline 位于：

```text
hci_image_analysis_skill/assets/cellprofiler/default_positive_w2.cppipe
```

该 pipeline 包含 `LoadData -> IdentifyPrimaryObjects(Nuclei) -> IdentifySecondaryObjects(Cells) -> IdentifyTertiaryObjects(Cytoplasm) -> MeasureObjectIntensity -> MeasureObjectSizeShape -> ExportToSpreadsheet`。运行时 `hci_hcs.py run --backend cellprofiler` 会把这个模板复制为本次输出目录下的 `runtime_default_positive_w2.cppipe`，并自动把 LoadData 指向本次 `cp_loaddata.csv`。
