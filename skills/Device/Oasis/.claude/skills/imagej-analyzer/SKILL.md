---
name: imagej-analyzer
description: Fiji/ImageJ 智能图像分析 - 支持荧光强度、细胞计数、共定位、3D 分析等多种分析模式
version: 2.0.0
---

# ImageJ Analyzer (Fiji 增强版)

基于 Fiji/ImageJ 的专业级智能图像分析工具。

## 触发条件

当用户的请求包含以下关键词或场景时触发此技能：

- **荧光分析**：荧光强度、免疫荧光、IF 染色
- **细胞计数**：细胞数量、细胞密度、细胞大小
- **伤口愈合**：划痕实验、细胞迁移、愈合率
- **Western Blot**：蛋白条带、灰度分析、表达量
- **菌落计数**：克隆形成、菌落数量
- **颗粒分析**：颗粒计数、粒径分布
- **共定位分析**：Pearson 系数、Manders 系数、双通道共定位
- **3D 分析**：体积测量、Z-stack、图像序列
- **通用图像分析**：图像统计、强度分布

## 可用命令

### 1. 智能分析（自动选择模式）

```bash
python .claude/skills/imagej-analyzer/scripts/analyze.py --image "<图像路径>" --task "<任务描述>"
```

示例：
```bash
# 细胞计数
python .claude/skills/imagej-analyzer/scripts/analyze.py --image "cells.png" --task "细胞计数"

# 荧光强度分析
python .claude/skills/imagej-analyzer/scripts/analyze.py --image "if.png" --task "免疫荧光强度分析"

# 共定位分析
python .claude/skills/imagej-analyzer/scripts/analyze.py --image "dual_channel.png" --task "共定位分析"
```

### 2. 指定模式分析

```bash
python .claude/skills/imagej-analyzer/scripts/analyze.py --image "<图像路径>" --mode "<模式>" [选项]
```

支持的模式：

| 模式 | 说明 | 输出指标 |
|------|------|---------|
| `fluorescence` | 荧光强度分析 | Mean Intensity, Integrated Density, 阳性细胞数 |
| `cell_count` | 细胞计数 | 细胞总数、密度、大小分布 |
| `wound_healing` | 伤口愈合 | 伤口面积、愈合率 |
| `western_blot` | Western Blot 分析 | 泳道数、条带强度 |
| `colony_count` | 菌落计数 | 菌落数量、大小分布 |
| `particle_analysis` | 颗粒分析 | 颗粒数量、粒径分布 |
| `colocalization` | 共定位分析 | Pearson 系数、Manders 系数 |
| `3d_analysis` | 3D 体积分析 | 体积、表面积 |
| `general` | 通用分析 | 平均/标准差/最小/最大强度 |

### 3. 高级选项

```bash
# 指定阈值算法
python .claude/skills/imagej-analyzer/scripts/analyze.py \
  --image "if.png" --mode "fluorescence" --threshold-method "otsu"

# 手动设置阈值
python .claude/skills/imagej-analyzer/scripts/analyze.py \
  --image "cells.png" --mode "cell_count" --threshold 128

# 暗背景模式（荧光图像）
python .claude/skills/imagej-analyzer/scripts/analyze.py \
  --image "if.png" --mode "fluorescence" --dark-background

# 颗粒尺寸范围
python .claude/skills/imagej-analyzer/scripts/analyze.py \
  --image "tem.png" --mode "particle_analysis" --min-size 10 --max-size 500

# 共定位分析指定通道
python .claude/skills/imagej-analyzer/scripts/analyze.py \
  --image "dual.png" --mode "colocalization" --channel1 "red" --channel2 "green"
```

**支持的阈值算法：**
- `otsu` - Otsu 自动阈值（默认）
- `triangle` - Triangle 算法（适合荧光图像）
- `li` - Li 算法（低信噪比）
- `huang` - Huang 算法（暗背景）
- `iso_data` - ISODATA 算法
- `max_entropy` - 最大熵阈值
- `mean` - 平均值阈值
- `default` - 固定阈值 128

### 4. 批量分析

```bash
python .claude/skills/imagej-analyzer/scripts/batch_analyze.py --input "<输入目录>" --output "<输出目录>" --mode "<模式>"
```

### 5. 生成报告

```bash
python .claude/skills/imagej-analyzer/scripts/generate_report.py --results "<结果文件>" --output "<报告文件>" --format "<格式>"
```

支持格式：`md`（默认）、`txt`、`json`

## 依赖

### Python 包

```
pyimagej>=1.4.0    # Fiji/ImageJ Python 接口
numpy>=1.20.0      # 数组操作
Pillow>=9.0.0      # 图像 I/O
scipy>=1.7.0       # 科学计算
```

安装：`pip install -r requirements.txt`

### Fiji/ImageJ

**推荐：使用新版 Fiji (2024 或更新版本)**

- 默认：从 [fiji.sc](https://fiji.sc/#download) 下载最新版 Fiji
- 相对路径：将 Fiji 放在 `../Fiji.app` 目录（skill 目录的上级）
- 配置：在 `utils/config.json` 中配置路径

新版 Fiji 特点：
- 包含 bundled JDK 21（无需单独安装 Java）
- 支持 headless 模式
- 自动检测 Java 环境

配置文件：`utils/config.json`

所有配置都保存在 skill 内部，无需设置环境变量，方便移植。

```json
{
  "fiji": {
    "path": null,
    "use_relative_path": true,
    "relative_path": "../Fiji.app",
    "memory": "4G",
    "headless": true,
    "auto_download": true
  },
  "analysis": {
    "default_threshold_method": "otsu",
    "default_dark_background": true,
    "calibration": {
      "pixel_width": 1.0,
      "pixel_height": 1.0,
      "unit": "pixel"
    }
  }
}
```

### Fiji 路径配置

**方式 1：相对路径（推荐）**
```json
{
  "fiji": {
    "use_relative_path": true,
    "relative_path": "../Fiji.app"
  }
}
```
将 Fiji 放在 skill 目录的上级目录（`skills/Fiji.app`）。
**注意：** 请下载新版 Fiji（2024 或更新版本），旧版 Fiji 可能与当前 pyimagej 不兼容。

**方式 2：自动下载**
```json
{
  "fiji": {
    "auto_download": true
  }
}
```
首次运行时自动下载 Fiji（约 500MB，需要 5-10 分钟）。

**方式 3：绝对路径**
```json
{
  "fiji": {
    "path": "C:\\Fiji.app",
    "use_relative_path": false
  }
}
```

### 已知问题

**TrackMate 插件警告**
```
Invalid service: fiji.plugin.trackmate.TrackMateService
UnsupportedClassVersionError: class file version 65.0
```
这是 TrackMate 插件需要 Java 21，而 pyimagej 使用的 Java 版本较低导致的。
**不影响核心功能**，可以忽略此警告。如需修复，可运行 Fiji 更新器更新所有插件。

## 输出格式

### 荧光强度分析输出示例

```json
{
  "mode": "fluorescence",
  "mean_intensity": 156.7,
  "std_intensity": 23.4,
  "integrated_density": 28140208.0,
  "positive_area": 15234,
  "positive_area_ratio": 0.35,
  "positive_cells": 127,
  "threshold_used": 163.0,
  "threshold_method": "otsu",
  "dark_background": true,
  "conclusion": "荧光强度中等，阳性细胞占比 35%"
}
```

### 共定位分析输出示例

```json
{
  "mode": "colocalization",
  "channel1": "red",
  "channel2": "green",
  "pearson_coefficient": 0.85,
  "manders_m1": 0.72,
  "manders_m2": 0.68,
  "colocalized_pixels": 15234,
  "colocalization_ratio": 0.42,
  "conclusion": "强共定位 (Pearson=0.85)"
}
```

### Western Blot 输出示例

```json
{
  "mode": "western_blot",
  "lane_count": 6,
  "lanes": [
    {"lane_id": 1, "bands": [{"position": 45, "intensity": 1234}]},
    ...
  ],
  "conclusion": "检测到 6 个泳道"
}
```

## 注意事项

1. **首次运行** - 需要下载 Fiji（约 500MB），需要 5-10 分钟
2. **内存设置** - 默认 4G 内存，大图像可在 `utils/config.json` 中修改 `fiji.memory` 参数（如 `"8G"`）
3. **荧光图像** - 默认使用暗背景模式 (Dark Background)
4. **阈值选择** - 荧光图像建议使用 `otsu` 或 `triangle` 算法
5. **Integrated Density** - 总荧光强度 = ROI 面积 × 平均强度
6. **图像格式** - 支持 TIFF、DICOM、PNG、JPEG、LSM、CZI 等

## 故障排除

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| Fiji 初始化失败 | 网络问题 | 检查网络连接，或手动下载 Fiji 并在 `config.json` 中配置 `fiji.path` |
| 内存不足 | 图像太大 | 在 `config.json` 中设置 `fiji.memory: "8G"` |
| 分析结果为 0 | 阈值不合适 | 调整 `--threshold` 参数或更换阈值方法 |
| 计数过多/过少 | 尺寸设置问题 | 调整 `--min-size` 和 `--max-size` 参数 |

## 相关资源

- [Fiji 官方网站](https://fiji.sc/)
- [ImageJ 官方文档](https://imagej.nih.gov/ij/docs/)
- [pyimagej 文档](https://imagej.net/pyimagej)

---

**版本：** 2.0.0 (Fiji 增强版)  
**最后更新：** 2026-04-10  
**维护者：** GUI Agent Team