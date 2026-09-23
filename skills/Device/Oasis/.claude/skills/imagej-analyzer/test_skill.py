# -*- coding: utf-8 -*-
"""测试 ImageJ Analyzer 技能"""
import sys
from pathlib import Path

# 添加父目录到路径以支持模块导入
sys.path.insert(0, str(Path(__file__).parent))

from utils.analyzer import ImageJAnalyzer, analyze_image

print("=" * 60)
print("ImageJ Analyzer 技能测试")
print("=" * 60)

# 测试 1: 创建分析器
print("\n[测试 1] 创建分析器...")
try:
    analyzer = ImageJAnalyzer()
    print("  [OK] 分析器创建成功")
except Exception as e:
    print("  [FAIL] 创建失败：{}".format(e))
    print("\n提示：首次运行需要等待 ImageJ 初始化（1-2 分钟）")
    sys.exit(1)

# 测试 2: 创建测试图像
print("\n[测试 2] 创建测试图像...")
import numpy as np
from PIL import Image

test_img = np.random.randint(50, 200, (200, 200), dtype=np.uint8)
test_path = Path(__file__).parent / "test_image.png"
Image.fromarray(test_img).save(test_path)
print("  [OK] 测试图像已创建")

# 测试 3: 智能分析（自动选择模式）
print("\n[测试 3] 测试智能分析（自动选择模式）...")
try:
    result = analyze_image(str(test_path), task="细胞计数")
    print("  模式：{}".format(result.get('mode')))
    print("  结论：{}".format(result.get('conclusion')))
    print("  [OK] 智能分析成功")
except Exception as e:
    print("  [FAIL] 分析失败：{}".format(e))

# 测试 4: 指定模式分析
print("\n[测试 4] 测试指定模式分析...")
try:
    result = analyze_image(str(test_path), mode="fluorescence")
    print("  模式：{}".format(result.get('mode')))
    print("  平均强度：{}".format(result.get('mean_intensity')))
    print("  结论：{}".format(result.get('conclusion')))
    print("  [OK] 指定模式分析成功")
except Exception as e:
    print("  [FAIL] 分析失败：{}".format(e))

# 测试 5: 保存结果
print("\n[测试 5] 保存分析结果...")
import json
try:
    result = analyze_image(str(test_path), mode="general")
    output_path = Path(__file__).parent / "test_result.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print("  结果已保存：{}".format(output_path))
    print("  [OK]")
except Exception as e:
    print("  [FAIL] 保存失败：{}".format(e))

# 清理
print("\n[清理] 删除测试文件...")
try:
    test_path.unlink()
    output_path.unlink()
    print("  [OK] 已清理")
except:
    pass

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)

print("\n可用命令:")
print("  # 智能分析")
print("  python scripts/analyze.py --image \"sample.png\" --task \"细胞计数\"")
print("")
print("  # 指定模式")
print("  python scripts/analyze.py --image \"sample.png\" --mode \"fluorescence\"")
print("")
print("  # 批量分析")
print("  python scripts/batch_analyze.py --input \"images/\" --output \"results/\"")
print("")
print("  # 生成报告")
print("  python scripts/generate_report.py --results \"results.json\" --output \"report.md\"")
