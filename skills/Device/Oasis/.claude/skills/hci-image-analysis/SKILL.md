---
name: hci-image-analysis
description: 分析按孔位、视野和 W1/W2 通道命名的高内涵细胞图像，完成细胞计数、荧光定量、QC和多后端比较。用户提供原始HCI图像、分组或position map，或要求比较skimage、CellProfiler、Cellpose时使用；普通单图、Western Blot、共定位和非板式图像分析使用imagej-analyzer。
metadata:
  short-description: W1/W2高内涵图像分析与三后端复核
---

# HCI 图像分析

用于 W1/W2 高内涵图像、MetaXpress MultiWaveScoring、CellProfiler、skimage 或 cellpose 分割，以及与 `Positive W2 Mean Cyto Integr Intens` 的对照分析。

## 参考资料

- 交接配置、输入格式、position map 和完整命令见 [README.md](README.md)。
- 输出字段、归一化和公式见 [指标字典](references/metrics_dictionary.md)。
- 三种方法选择及指标解释见 [方法说明](references/method_notes.md)。

## 分析前必须确认

1. 核对文件名是否符合 `实验名_孔位_s视野_w通道*.tif`。
2. 确认 `w1` 是核通道、`w2` 是 BODIPY/Marker/细胞质通道；不能只凭颜色推断。
3. 确认分组规则。`bc` 表示 B 行对照、C 行模型、D–G 行处理；`bodipy0513` 表示 B 行 BSA、C 行 FM、D–G 行药物；未知板图使用 `none`。
4. 药物筛选优先使用 position map/plate map。最低只需 `well` 列；`compound`、`dose`、`replicate`、`treatment_set` 等额外字段必须原样保留，不得补造。
5. 默认期望每孔四个视野 `s1`–`s4`。生成 manifest 后检查孔位、视野及 W1/W2 配对覆盖率。
6. 文件名不符合默认规则时，先取得代表性文件名或板图，再扩展解析器。

## 环境检测与正式运行

下文命令里的 `scripts/` 指本技能目录下的脚本：在工作区运行时写成 `python .claude/skills/hci-image-analysis/scripts/...`，输出写到工作区的 `outputs/` 下。平台会自动选择本技能的 Python 环境，不要激活其他环境或自行安装包。

首次在当前Python环境运行，或迁移到新服务器后，先执行只读检测：

```bash
python .claude/skills/hci-image-analysis/scripts/check_environment.py --json-output outputs/environment_check.json
```

检测确认skimage必需依赖、默认CellProfiler pipeline和可选后端状态，不读取实验图像。必要检查通过后，再执行下面的正式分析。CellProfiler或Cellpose缺失只影响对应可选后端，不阻止skimage流程。

## 标准流程

### 1. 生成输入清单

```bash
python scripts/hci_hcs.py prepare \
  --image-root /path/to/images \
  --position-map /path/to/plate_map.xlsx \
  --group-mode bc \
  --out outputs/run_x
```

`--position-map` 可省略。命令生成 `manifest.csv` 和供 CellProfiler 使用的 `cp_loaddata.csv`。后续后端必须使用 manifest，不再重新猜测文件路径和孔位。

### 2. 选择分析后端

CellProfiler 可用时，优先运行推荐生产流程。技能已内置 `assets/cellprofiler/default_positive_w2.cppipe`，通常无需传入 `--pipeline`：

```bash
python scripts/hci_hcs.py run \
  --backend cellprofiler \
  --manifest outputs/run_x/manifest.csv \
  --out outputs/run_x/cellprofiler
```

CellProfiler 暂未安装时，使用 skimage 完成 manifest、对象、视野、孔级、QC 和软件对照全流程，并在报告中明确实际后端：

```bash
python scripts/hci_hcs.py run \
  --backend skimage \
  --manifest outputs/run_x/manifest.csv \
  --out outputs/run_x/skimage
```

cellpose 用于争议孔、细胞成团或核分割复核。优先运行小范围孔位：

```bash
python scripts/hci_hcs.py run \
  --backend cellpose \
  --manifest outputs/run_x/manifest.csv \
  --wells B02,C02,D04 \
  --out outputs/run_x/cellpose
```

### 3. 对比与质控

```bash
python scripts/hci_hcs.py compare-backends \
  --inputs outputs/run_x/cellprofiler outputs/run_x/skimage outputs/run_x/cellpose \
  --out outputs/run_x

python scripts/hci_hcs.py compare-software \
  --scores outputs/run_x/per_well_metrics.csv \
  --software-root /path/to/software_excels \
  --out outputs/run_x

python scripts/hci_hcs.py qc-report \
  --scores outputs/run_x/per_well_metrics.csv \
  --out outputs/run_x/qc
```

仅比较实际完成的后端。少于两种后端时，不得声称已完成多方法对比。

## 三种后端的角色

- `cellprofiler`：推荐生产路线。适合批量跑板、对象级输出和软件指标复现；默认使用内置 pipeline。
- `skimage`：无需 CellProfiler 的完整开源路线，也用于快速复核和稳健的 `per_area` 测量。
- `cellpose`：可选深度学习复核路线，适合争议孔和成团孔；CPU 较慢，默认不全板运行。

缺少 CellProfiler 或 cellpose 不能阻止 skimage 完成分析，但报告必须列出实际运行、未运行的方法及原因。

## 指标与解释

CellProfiler 软件复现的默认校准指标：

- `calibrated_integr_p95_1p25`
- `calibrated_integr_p95_1p30`

必须将它们标记为校准型指标，不能表述为独立原始生物学测量。同时保留：

- `integr_p95`：CellProfiler 对象尾部指标；
- `top50_integr_mean`：positive-object 基线指标；
- `per_area`：细胞质单位面积信号，用于计数不稳或成团孔；
- `site_cv`：同孔视野间波动。`site_cv > 0.5` 只表示高视野波动，未经目视检查不得称为模糊图。

## 报告要求

- 列明图像命名规则、通道含义、分组来源和 position map 使用情况。
- 列明实际运行的后端、未运行后端及原因。
- 分开呈现独立指标与校准指标。
- 有软件 Excel 时报告 raw Pearson、log10 Pearson、Spearman、分析 C/B、软件 C/B 和 C/B 绝对误差。
- 没有软件 Excel 时，只报告后端结果、开放流程 C/B 和 QC。
- 没有 plate map 时只能按孔位报告，不能把处理孔解释成具体药物、剂量或重复。
- 输出至少包括 manifest、每视野表、每孔表、对象表、QC 表；多后端或软件结果存在时再输出相应对比表。
