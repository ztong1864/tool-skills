#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量图像分析脚本

用法:
    python batch_analyze.py --input "images/" --mode "cell_count" --output "results/"
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# 添加父目录到路径以支持模块导入
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir.parent))

from utils.analyzer import ImageJAnalyzer

def main():
    parser = argparse.ArgumentParser(description="批量图像分析")
    
    parser.add_argument("--input", "-i", required=True, help="输入图像目录")
    parser.add_argument("--output", "-o", required=True, help="输出结果目录")
    parser.add_argument("--mode", "-m", default="general", help="分析模式")
    parser.add_argument("--pattern", default="*.png", help="文件匹配模式")
    parser.add_argument("--recursive", "-r", action="store_true", help="递归搜索子目录")
    
    args = parser.parse_args()
    
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("批量图像分析")
    print("=" * 60)
    print("\n输入目录：{}".format(input_dir))
    print("输出目录：{}".format(output_dir))
    print("分析模式：{}".format(args.mode))
    
    # 查找图像文件
    if args.recursive:
        image_files = list(input_dir.rglob(args.pattern))
    else:
        image_files = list(input_dir.glob(args.pattern))
    
    print("\n找到 {} 个图像文件".format(len(image_files)))
    
    if not image_files:
        print("未找到图像文件")
        sys.exit(0)
    
    # 创建分析器
    analyzer = ImageJAnalyzer()
    
    # 批量分析
    results = []
    success_count = 0
    error_count = 0
    
    print("\n开始分析...")
    
    for i, image_file in enumerate(image_files, 1):
        print("[{}/{}] 分析：{}".format(i, len(image_files), image_file.name))
        
        try:
            result = analyzer.analyze(str(image_file), mode=args.mode)
            results.append(result)
            
            # 保存单个结果
            output_file = output_dir / (image_file.stem + "_result.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            success_count += 1
            
        except Exception as e:
            print("  失败：{}".format(e))
            results.append({
                'image': str(image_file),
                'error': str(e)
            })
            error_count += 1
    
    # 保存汇总结果
    summary = {
        'timestamp': datetime.now().isoformat(),
        'input_dir': str(input_dir),
        'output_dir': str(output_dir),
        'mode': args.mode,
        'total_files': len(image_files),
        'success_count': success_count,
        'error_count': error_count,
        'results': results
    }
    
    summary_file = output_dir / "summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print("批量分析完成")
    print("=" * 60)
    print("成功：{} 个".format(success_count))
    print("失败：{} 个".format(error_count))
    print("汇总结果：{}".format(summary_file))


if __name__ == "__main__":
    main()
