#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ImageJ Analyzer - 智能图像分析主脚本

用法:
    python analyze.py --image "sample.png" --task "细胞计数"
    python analyze.py --image "sample.png" --mode "fluorescence"
    python analyze.py --image "sample.png" --mode "cell_count" --output "result.json"
"""
import sys
import json
import argparse
from pathlib import Path

# 添加父目录到路径以支持模块导入
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir.parent))

from utils.analyzer import ImageJAnalyzer, analyze_image, to_python_type

def main():
    parser = argparse.ArgumentParser(
        description="ImageJ 智能图像分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 自动分析（根据任务描述选择模式）
  python analyze.py --image "sample.png" --task "细胞计数"
  
  # 指定分析模式
  python analyze.py --image "sample.png" --mode "fluorescence"
  
  # 输出结果到文件
  python analyze.py --image "sample.png" --mode "cell_count" --output "result.json"
  
  # 自定义参数
  python analyze.py --image "sample.png" --mode "cell_count" --min-size 20 --max-size 500
        """
    )

    # 输入参数
    parser.add_argument("--image", "-i", required=True, help="输入图像路径")
    parser.add_argument("--task", "-t", help="任务描述（用于自动选择分析模式）")
    parser.add_argument("--mode", "-m", help="分析模式（fluorescence/cell_count/wound_healing 等）")

    # 输出参数
    parser.add_argument("--output", "-o", help="输出结果文件路径（JSON 格式）")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    # 阈值参数
    parser.add_argument("--threshold", type=float, help="手动设置阈值")
    parser.add_argument("--threshold-method", choices=['otsu', 'triangle', 'mean', 'default'],
                        default='otsu', help="阈值算法（默认：otsu）")
    parser.add_argument("--dark-background", action="store_true",
                        help="暗背景模式（荧光图像默认启用）")

    # 通用参数
    parser.add_argument("--min-size", type=float, help="最小分析尺寸")
    parser.add_argument("--max-size", type=float, help="最大分析尺寸")

    args = parser.parse_args()

    # 检查图像文件
    image_path = Path(args.image)
    if not image_path.exists():
        print("错误：图像文件不存在：{}".format(image_path))
        sys.exit(1)

    print("=" * 60)
    print("ImageJ 智能图像分析")
    print("=" * 60)
    print("\n图像：{}".format(image_path))
    print("任务：{}".format(args.task if args.task else "未指定"))
    print("模式：{}".format(args.mode if args.mode else "自动选择"))

    # 准备参数
    params = {}
    if args.min_size:
        params['min_size'] = args.min_size
    if args.max_size:
        params['max_size'] = args.max_size
    if args.threshold:
        params['threshold'] = args.threshold
    if args.threshold_method:
        params['threshold_method'] = args.threshold_method
    if args.dark_background:
        params['dark_background'] = True
    
    # 执行分析
    print("\n正在分析...")
    try:
        result = analyze_image(
            str(image_path),
            task=args.task,
            mode=args.mode,
            params=params if params else None
        )
        
        # 输出结果
        print("\n" + "=" * 60)
        print("分析结果")
        print("=" * 60)

        # 显示关键结果
        if 'total_cells' in result:
            print("\n细胞总数：{}".format(result['total_cells']))
        if 'mean_intensity' in result:
            print("平均强度：{:.1f}".format(result['mean_intensity']))
        if 'integrated_density' in result:
            print("总荧光强度 (Integrated Density): {:.1f}".format(result['integrated_density']))
        if 'particle_count' in result:
            print("颗粒数量：{}".format(result['particle_count']))
        if 'colony_count' in result:
            print("菌落数量：{}".format(result['colony_count']))
        if 'healing_rate' in result:
            print("愈合率：{:.1%}".format(result['healing_rate']))

        # 显示阈值信息
        if 'threshold_used' in result:
            print("\n阈值：{:.1f} ({})".format(
                result['threshold_used'],
                result.get('threshold_method', 'auto')
            ))

        # 显示结论
        if 'conclusion' in result:
            print("\n结论：{}".format(result['conclusion']))

        # 保存到文件
        if args.output:
            output_path = Path(args.output)
            # 转换为 Python 原生类型
            result_py = to_python_type(result)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result_py, f, indent=2, ensure_ascii=False)
            print("\n结果已保存：{}".format(output_path))

        # 显示完整结果（verbose 模式）
        if args.verbose:
            print("\n完整结果:")
            # 转换为 Python 原生类型
            result_py = to_python_type(result)
            print(json.dumps(result_py, indent=2, ensure_ascii=False))

        print("\n" + "=" * 60)
        
    except Exception as e:
        print("\n分析失败：{}".format(e))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
