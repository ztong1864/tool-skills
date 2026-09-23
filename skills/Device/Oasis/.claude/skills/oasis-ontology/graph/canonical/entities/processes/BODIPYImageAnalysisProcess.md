# Process: BODIPY 图像分析流程
id: process-bodipy-image-analysis
description: 用于对 BODIPY 多视野双通道图像执行核计数、绿光强度计算、单孔平均、BSA 归一化与 FM 阈值筛选的标准流程实例。

## Step 1: 读取输入数据
- type: input_preparation
- purpose: 收集待分析图像目录、板图 Excel 和输出目录。
- input:
  - `BODIPY_0513/` 图像目录
  - `top40_obesity_disorder_Test.xlsx` 板图文件
- output:
  - 可用于批量解析的图像文件列表
  - 孔位到组别的板图映射

## Step 2: 解析图像命名
- type: file_parsing
- purpose: 从文件名中解析实验名、孔位、视野号和通道号。
- rule:
  - 第 1 段为实验名
  - 第 2 段为孔位，如 `B02` 到 `G11`
  - 第 3 段为视野号，如 `s1` 到 `s4`
  - `w1` 为蓝色核通道
  - `w2` 为绿色 BODIPY 通道
- output:
  - 每个 `experiment + well + field` 对应的一对 `w1/w2` 图像

## Step 3: 解析板图与对照组
- type: metadata_mapping
- purpose: 从板图中识别每个孔位对应的药物或对照类型，并确定 BSA 与 FM。
- rule:
  - `BM` 视为 BSA 组
  - `FM` 视为 FM 对照组
  - 当前板图采用矩阵映射：`Sheet1!B5:K10` 对应 `B02:G11`
- output:
  - BSA 孔位集合
  - FM 孔位集合
  - 孔位到药物名/组别的映射

## Step 4: 蓝色通道核计数
- type: image_analysis
- purpose: 对每个视野的 `w1` 蓝色通道图像计数细胞核。
- method:
  - 高斯平滑
  - Otsu 阈值分割
  - 小目标过滤
  - 距离变换 + 分水岭分割
- metric:
  - `blue_count`

## Step 5: 绿色通道强度计算
- type: image_analysis
- purpose: 对每个视野的 `w2` 绿色通道图像计算背景扣除后的总强度。
- method:
  - 取第 10 百分位作为背景
  - 从原图中扣除背景
  - 计算背景扣除后的积分强度
- metric:
  - `green_intensity`

## Step 6: 计算单视野绿光强度/细胞
- type: metric_calculation
- purpose: 用绿色总强度除以蓝色核计数，得到单视野单位细胞绿光强度。
- formula:
  - `green_per_cell = green_intensity / blue_count`
- note:
  - 如果 `blue_count = 0`，该视野记为无效，不参与后续平均

## Step 7: 计算单孔平均值
- type: aggregation
- purpose: 对同一孔的 4 个视野 `green_per_cell` 取平均，得到单孔指标。
- formula:
  - `well_mean_green_per_cell = mean(field_green_per_cell_1..4)`

## Step 8: BSA 归一化
- type: normalization
- purpose: 将所有单孔指标归一化到 BSA 组平均值上。
- formula:
  - `normalized_to_bsa = well_mean_green_per_cell / mean(BSA wells)`
- interpretation:
  - BSA 组整体均值归一化后定义为 `1`

## Step 9: FM 阈值筛选
- type: threshold_screening
- purpose: 计算 FM 对照组均值，并筛选低于 FM 组均值的候选药物。
- formula:
  - `fm_mean = mean(FM wells)`
- interpretation:
  - 若实验目标是 “BODIPY 值越低越好”，则 `well_mean_green_per_cell < fm_mean` 的药物可视为优先候选

## Step 10: 输出结果与报告
- type: reporting
- purpose: 输出视野级、孔级和汇总级结果，并生成结构化报告。
- output:
  - `data-bodipy-0513-analysis-result`
  - `field_metrics.json`
  - `well_metrics.json`
  - `summary.json`
  - `BODIPY_0513_report.md`
