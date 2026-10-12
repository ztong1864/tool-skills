# Metrics Dictionary

| 字段 | 定义 | 备注 |
|---|---|---|
| `cell_count` | 每个 site 或每孔平均核数 | W1/nucleus 通道得到 |
| `n_measured` | 有效细胞质对象数 | 可能小于核数 |
| `mean_integr` | 对象 W2 cytoplasm integrated intensity 平均 | 每细胞积分强度 |
| `total_integr` | 所有细胞质对象 W2 integrated intensity 总和 | 总信号 |
| `total_area` | 所有细胞质对象面积总和 | 像素数 |
| `per_area` | `total_integr / total_area` | 不依赖细胞计数 |
| `site_cv` | 同孔 4 个 site 的 `mean_integr` CV | `>0.5` 标记高波动 |
| `top50_integr_mean` | 每孔 `integr_raw` 最高 50% 对象的平均 | CellProfiler baseline |
| `top25_integr_mean` | 每孔 `integr_raw` 最高 25% 对象的平均 | object-tail 指标 |
| `integr_p95` | 每孔 `integr_raw` 第 95 百分位 | 独立 object-tail 指标 |
| `integr_p98` | 每孔 `integr_raw` 第 98 百分位 | 更极端尾部 |
| `calibrated_integr_p95_1p25` | `integr_p95 ^ 1.25` | 软件复现/校准型 |
| `calibrated_integr_p95_1p30` | `integr_p95 ^ 1.30` | 软件复现/校准型 |
| `raw_pearson` | CP/开源指标与软件原值 Pearson 相关 | 受极端值影响 |
| `log10_pearson` | log10 后 Pearson 相关 | 更适合跨数量级比较 |
| `spearman` | 秩相关 | 衡量排序一致性 |
| `CP C/B` | C 行 model 均值 / B 行 control 均值 | 模型/对照对比度 |
| `software C/B` | 软件 C 行均值 / 软件 B 行均值 | 软件对比度 |

`integr_raw` 的 CellProfiler 定义：

```text
integr_raw = Intensity_IntegratedIntensity_Marker * Scaling_Marker
```

`per_area` 的定义：

```text
per_area = sum(integr_raw) / sum(cytoplasm_area)
```


CellProfiler 输出 `per_area` 需要 `MyExpt_Cytoplasm.csv` 中存在 `AreaShape_Area`。如果 pipeline 没有 MeasureObjectSizeShape，`per_area` 会为空，应改跑带 SizeShape 的 pipeline 或用 skimage/cellpose backend 复核。

## Data And Grouping Fields

| 字段 | 定义 | 备注 |
|---|---|---|
| `experiment` | 从文件名中孔位前的部分解析得到的实验名/板编号 | 如 `0513-2`、`0602-7-1-1` |
| `acquisition` | 从目录层级推断的采集批次或板目录名 | 用于多板/多批次合并 |
| `well` | 96 孔板孔位 | 如 `B02` |
| `site` | 视野编号 | 如 `1`，通常每孔 `s1-s4` |
| `channel` | 图像通道 | `w1=nucleus`，`w2=marker/cytoplasm` |
| `group` | 分组标签 | 0609: `control/model/treat`; BODIPY 0513: `BSA/FM/drug`; position map 中提供时优先使用 |
| `date_batch` | 从 acquisition 名称中解析的日期/批次字段 | 如 `0609 1-1 15-2` 中的 `0609` |
| `plate_repeat` | 从 acquisition 名称中解析的板/重复字段 | 如 `0609 1-1 15-2` 中的 `1-1` |
| `treatment_set` | 从 acquisition 名称中解析的处理编号 | 如 `0609 1-1 15-2` 中的 `15-2` |
| `compound` | position map 提供的药物名或药物编号 | 可为空，不由程序猜测 |
| `dose` | position map 提供的剂量 | 可为空 |
| `dose_unit` | position map 提供的剂量单位 | 如 `uM` |
| `replicate` | position map 提供的复孔或生物重复编号 | 可为空 |
| `normalized_to_bsa` | BODIPY 场景中孔值除以 BSA 组均值 | 越低表示单位细胞 BODIPY 绿光越低 |
| `normalized_to_model` | Positive W2 场景中孔值除以模型组均值 | 模型组约为 1 |
| `recovery` | `(孔值 - 模型均值) / (模型均值 - 对照均值)` | 负值表示往对照方向回复 |
