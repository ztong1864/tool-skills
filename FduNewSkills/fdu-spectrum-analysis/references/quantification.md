# 输入格式与定量规则

## 1. JSON 输入

输入为单个样品对象，或 `{"samples": [样品对象, ...]}`。每个对象必须有 `sample_id`、`method`。同一批次样品编号唯一。同一样品采用多种方法时，使用不同记录编号并在 `experiment_id` 中关联。

| 字段 | 说明 |
|---|---|
| `experiment_id`、`sample_id` | 实验与分析记录编号 |
| `method` | `qnmr`、`chromatography_internal_standard`、`chromatography_external_standard`、`isolated_mass`、`area_fraction` 或 `qualitative` |
| `theoretical_product_mmol` | 理论产物物质的量，可直接提供 |
| `limiting_reagent` | 未直接给理论量时，提供 `amount_mmol`、`stoichiometric_coefficient`，并提供 `product_stoichiometric_coefficient` |
| `sampling` | 定量方法采用 `aliquot_to_total_factor` 和 `basis`：实测份样对应到全反应产物量的倍数和依据 |
| `initial_substrate_mmol` | 可选；转化率计算的实际底物初始量 |
| `remaining_substrate_mmol` | 可选；已校准的全反应剩余底物量，与初始量对应同一种底物 |
| `evidence` | 文件路径、页码、仪器峰编号或实验记录位置 |

`aliquot_to_total_factor` 明确填写。分析整份反应产物，或全反应加入内标后取代表性样品测积分比时，填 `1`；仅在取出的份样中加入内标时，按份样代表的全反应比例放大。均匀性、回收率和取样依据需记录。普通稀释改变浓度，物质的量是否放大由实际取样流程确定。

所有数值采用有限数，mg、g/mol、mmol、mL、mmol/L、百分比的单位按字段规定填写。纯度采用 0～1 的质量分数。`0` 是测量值，缺失值用 `null`。脚本返回 `complete`、`partial`、`qualitative` 或 `invalid` 计算状态，及缺失/异常字段。

## 2. qNMR 内标法

```json
{
  "sample_id": "example-qnmr",
  "experiment_id": "example-only",
  "method": "qnmr",
  "theoretical_product_mmol": 0.1,
  "sampling": {"aliquot_to_total_factor": 1, "basis": "全反应加入内标后取样"},
  "standard": {"mass_mg": 3.0, "molar_mass_g_mol": 150.0, "purity_fraction": 1.0},
  "standard_signal": {"integral": 3.0, "nuclei_count": 3},
  "product_signal": {"integral": 4.0, "nuclei_count": 1},
  "quantitation_checks": {"nonoverlapping_signals": true, "quantitative_acquisition": true},
  "evidence": [{"file": "example_measurement_record", "note": "仅为输入格式及公式示例"}]
}
```

该组数值用于展示公式，计算产物 0.08 mmol、qNMR 产率 80%。真实实验采用实际分子量、测量积分、内标纯度和采集条件。`standard` 可改用已明确纯度修正的 `amount_mmol`；该值为用于积分比定量的内标有效物质的量。

计算公式：

```text
n_standard(mmol) = mass_mg / molar_mass_g_mol × purity_fraction
n_product_total(mmol) = (I_product / N_product) / (I_standard / N_standard)
                        × n_standard × aliquot_to_total_factor
yield_percent = n_product_total / theoretical_product_mmol × 100
```

`nuclei_count` 表示所选积分信号代表的核数；多重峰采用整个信号的积分。¹H qNMR 使用验证的定量采集条件，检查弛豫、相位、基线、信噪比和峰重叠。两个 `quantitation_checks` 必须为 `true` 才形成可用定量结论。可选 `substrate_signal` 使用同一内标计算全反应剩余底物量。

理论量由限量试剂和化学计量计算：

```text
n_theoretical_product = n_limiting × ν_product / ν_limiting
```

## 3. 色谱内标法

`method = chromatography_internal_standard`，提供 `standard`（同上）、`standard_peak_area`、`product_peak_area`、`relative_response_factor`、`sampling` 和理论产物量。

本脚本统一定义：

```text
RRF = (A_product / n_product) / (A_standard / n_standard)
n_product_total = (A_product / A_standard) / RRF × n_standard × aliquot_to_total_factor
```

填写 `response_factor_definition = "(A_product/n_product)/(A_standard/n_standard)"` 和 `calibration_source`，记录验证响应因子的标准品/文件。仪器软件采用其他约定时，先转换响应因子再输入。

## 4. 色谱外标法

`method = chromatography_external_standard`，提供 `product_peak_area`、`calibration` 和 `sampling`。

```json
{
  "calibration": {
    "slope_area_per_mmol_L": 1000,
    "intercept_area": 0,
    "min_concentration_mmol_L": 0.01,
    "max_concentration_mmol_L": 2.0,
    "source": "实际标准曲线文件"
  },
  "solution_volume_ml": 1.0,
  "dilution_factor": 10,
  "sampling": {"aliquot_to_total_factor": 1, "basis": "整份样品配成1mL后，取样稀释10倍测量"}
}
```

```text
c_measured(mmol/L) = (A_product - intercept) / slope
n_product_total(mmol) = c_measured × dilution_factor × solution_volume_ml / 1000
                        × aliquot_to_total_factor
```

`solution_volume_ml` 为稀释前配制的样品溶液总体积，`dilution_factor` 为该溶液到最终测量溶液的浓度稀释倍数；份样放大与溶液稀释分别计量。浓度超出校准范围时，脚本保留算术值并标记待复核。

## 5. 分离产物质量法

`method = isolated_mass`，提供 `product_mass_mg`、`product_molar_mass_g_mol` 和理论产物量。填写 `mass_basis = "entire_isolated_product"`，质量对应干燥后的整份分离产物；含溶剂或仅称份样时，先取得相应记录。

```text
n_product(mmol) = product_mass_mg / product_molar_mass_g_mol
isolated_yield_percent = n_product / theoretical_product_mmol × 100
```

提供独立测得的 `product_purity_fraction` 和 `product_purity_source` 时另算 `purity_corrected_isolated_yield_percent`。色谱面积占比仅在验证可对应质量纯度时用于该纯度字段，并记录验证来源。

## 6. 转化率和面积占比

```text
conversion_percent = (initial_substrate_mmol - remaining_substrate_mmol)
                     / initial_substrate_mmol × 100
```

底物初始量和剩余量采用同一实际反应口径。来自 qNMR 的剩余底物量与手动输入同时存在且不一致时，记录冲突并复核。产率和转化率分别统计。

`method = area_fraction` 时提供 `product_peak_area`、`total_included_peak_area` 和 `included_peaks_basis`（如排除溶剂、内标的样品峰）。输出 `chromatographic_area_fraction_percent`。

产率大于 100%、剩余底物大于初始量、面积占比大于 100% 等保留原算术值并标记异常；复核后再形成实验结论。

## 7. 方法依据

- [BIPM：qNMR 内标参考数据与测量指南](https://www.bipm.org/documents/20126/27085544/bipm%20publication-ID-3285.pdf/ec019517-6a18-0c88-6024-0a3548ff4c7e?download=true&t=1607934454240&version=1.8)：按积分比、信号核数、内标量与纯度建立定量关系，并检查采集和积分条件。
- [NIST：用于定量 NMR 的苯甲酸一级标准](https://www.nist.gov/publications/new-realization-si-organic-chemical-measurement-nist-ps1-primary-standard-quantitative)：定量校准采用有明确量值依据的标准物质。

上述指南支持定量关系与校准要求。本 Skill 将实测产物量进一步与反应理论产物量对应，得到相应方法的产率。
