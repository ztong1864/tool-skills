#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成分析报告脚本

用法:
    python generate_report.py --results "results.json" --output "report.pdf"
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(description="生成分析报告")
    
    parser.add_argument("--results", "-r", required=True, help="结果文件路径（JSON）")
    parser.add_argument("--output", "-o", required=True, help="输出报告路径")
    parser.add_argument("--format", "-f", choices=['txt', 'md', 'json'], default='md', help="报告格式")
    
    args = parser.parse_args()
    
    # 读取结果
    results_file = Path(args.results)
    if not results_file.exists():
        print("错误：结果文件不存在：{}".format(results_file))
        sys.exit(1)
    
    with open(results_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 生成报告
    output_path = Path(args.output)
    
    if args.format == 'md':
        report = generate_markdown_report(data)
        output_path = output_path.with_suffix('.md')
    elif args.format == 'txt':
        report = generate_text_report(data)
        output_path = output_path.with_suffix('.txt')
    else:
        report = json.dumps(data, indent=2, ensure_ascii=False)
        output_path = output_path.with_suffix('.json')
    
    # 保存报告
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print("=" * 60)
    print("报告生成完成")
    print("=" * 60)
    print("输出文件：{}".format(output_path))


def generate_markdown_report(data):
    """生成 Markdown 格式报告"""
    report = []
    
    report.append("# 图像分析报告")
    report.append("")
    report.append("**生成时间：** {}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    report.append("")
    
    # 判断是单个结果还是批量结果
    if 'results' in data and isinstance(data['results'], list):
        # 批量分析
        report.append("## 汇总信息")
        report.append("")
        report.append("- **总文件数：** {}".format(data.get('total_files', 0)))
        report.append("- **成功：** {}".format(data.get('success_count', 0)))
        report.append("- **失败：** {}".format(data.get('error_count', 0)))
        report.append("- **分析模式：** {}".format(data.get('mode', 'N/A')))
        report.append("")
        
        report.append("## 详细结果")
        report.append("")
        
        for i, result in enumerate(data['results'], 1):
            if 'error' in result:
                continue
            
            report.append("### {}. {}".format(i, Path(result.get('image', '')).name))
            report.append("")
            
            # 添加关键指标
            for key, value in result.items():
                if key not in ['image', 'timestamp', 'parameters', 'histogram', 'centroids']:
                    if isinstance(value, float):
                        report.append("- **{}：** {:.2f}".format(key, value))
                    else:
                        report.append("- **{}：** {}".format(key, value))
            
            # 添加结论
            if 'conclusion' in result:
                report.append("")
                report.append("> **结论：** {}".format(result['conclusion']))
            
            report.append("")
    
    else:
        # 单个分析
        report.append("## 分析结果")
        report.append("")
        report.append("- **图像：** {}".format(data.get('image', 'N/A')))
        report.append("- **模式：** {}".format(data.get('mode', 'N/A')))
        report.append("- **时间：** {}".format(data.get('timestamp', 'N/A')))
        report.append("")
        
        report.append("### 关键指标")
        report.append("")
        
        for key, value in data.items():
            if key not in ['image', 'timestamp', 'parameters', 'histogram', 'centroids', 'mode', 'conclusion']:
                if isinstance(value, float):
                    report.append("- **{}：** {:.2f}".format(key, value))
                else:
                    report.append("- **{}：** {}".format(key, value))
        
        report.append("")
        
        # 结论
        if 'conclusion' in data:
            report.append("## 结论")
            report.append("")
            report.append("> {}".format(data['conclusion']))
            report.append("")
    
    report.append("---")
    report.append("*报告由 ImageJ Analyzer 自动生成*")
    
    return '\n'.join(report)


def generate_text_report(data):
    """生成纯文本报告"""
    lines = []
    
    lines.append("=" * 60)
    lines.append("图像分析报告")
    lines.append("=" * 60)
    lines.append("")
    lines.append("生成时间：{}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    lines.append("")
    
    if 'results' in data:
        # 批量分析
        lines.append("汇总信息")
        lines.append("-" * 40)
        lines.append("总文件数：{}".format(data.get('total_files', 0)))
        lines.append("成功：{}".format(data.get('success_count', 0)))
        lines.append("失败：{}".format(data.get('error_count', 0)))
        lines.append("")
        
        for i, result in enumerate(data['results'], 1):
            if 'error' in result:
                continue
            
            lines.append("{}. {}".format(i, Path(result.get('image', '')).name))
            if 'conclusion' in result:
                lines.append("   结论：{}".format(result['conclusion']))
        
    else:
        # 单个分析
        lines.append("分析结果")
        lines.append("-" * 40)
        lines.append("图像：{}".format(data.get('image', 'N/A')))
        lines.append("模式：{}".format(data.get('mode', 'N/A')))
        lines.append("")
        
        if 'conclusion' in data:
            lines.append("结论：{}".format(data['conclusion']))
    
    lines.append("")
    lines.append("=" * 60)
    
    return '\n'.join(lines)


if __name__ == "__main__":
    main()
