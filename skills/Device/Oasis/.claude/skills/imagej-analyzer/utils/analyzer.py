# -*- coding: utf-8 -*-
"""
ImageJ Analyzer - 智能图像分析核心模块
支持自动分析决策和多种分析模式

使用 Fiji/ImageJ 进行专业图像分析，支持：
- 多通道荧光分析
- 颗粒分析（带校准）
- Western Blot 泳道检测
- 伤口愈合分析
- 共定位分析
- 3D 体积分析
"""
import sys
import json
import numpy as np
from pathlib import Path
from datetime import datetime

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

# numpy 类型转 Python 原生类型的辅助函数
def to_python_type(obj):
    """将 numpy 类型转换为 Python 原生类型，便于 JSON 序列化"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: to_python_type(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [to_python_type(item) for item in obj]
    return obj

# 导入处理器（自动 Fiji 或 fallback）
from vision.imagej_processor import ImageJProcessor, get_processor, HAS_IMAGEJ

try:
    from config import load_config, get_calibration
except ImportError:
    def load_config():
        return {}
    def get_calibration():
        return {'pixel_width': 1.0, 'pixel_height': 1.0, 'unit': 'pixel'}


def log(msg):
    """Log message"""
    print(msg)


class AnalysisDecision:
    """分析决策引擎"""

    # 任务类型到分析模式的映射
    TASK_TO_MODE = {
        # 荧光相关
        '荧光': 'fluorescence',
        'fluorescence': 'fluorescence',
        'if': 'fluorescence',
        '免疫荧光': 'fluorescence',

        # 细胞计数
        '细胞': 'cell_count',
        'cell': 'cell_count',
        '计数': 'cell_count',
        'count': 'cell_count',

        # 伤口愈合
        '伤口': 'wound_healing',
        'wound': 'wound_healing',
        '划痕': 'wound_healing',
        '迁移': 'wound_healing',

        # Western Blot
        'western': 'western_blot',
        'blot': 'western_blot',
        '蛋白': 'western_blot',
        '条带': 'western_blot',
        'band': 'western_blot',

        # 菌落计数
        '菌落': 'colony_count',
        'colony': 'colony_count',
        '克隆': 'colony_count',

        # 颗粒分析
        '颗粒': 'particle_analysis',
        'particle': 'particle_analysis',
        '微泡': 'particle_analysis',

        # 共定位分析（新增）
        '共定位': 'colocalization',
        'colocalization': 'colocalization',
        'coloc': 'colocalization',

        # 3D 分析（新增）
        '3d': '3d_analysis',
        '3D': '3d_analysis',
        '体积': '3d_analysis',
        'stack': '3d_analysis',

        # 通用分析
        '通用': 'general',
        'general': 'general',
        'default': 'general',
    }

    @classmethod
    def decide_mode(cls, task_description, image_info=None):
        """根据任务描述决定分析模式"""
        task_lower = task_description.lower()

        for keyword, mode in cls.TASK_TO_MODE.items():
            if keyword.lower() in task_lower:
                log(f"根据关键词 '{keyword}' 选择模式：{mode}")
                return mode

        log("未匹配到特定模式，使用通用模式")
        return 'general'

    @classmethod
    def get_default_params(cls, mode):
        """获取模式的默认参数"""
        params = {
            'fluorescence': {
                'threshold_method': 'otsu',
                'min_intensity': 50,
                'measure_mean': True,
                'measure_std': True,
                'dark_background': True,
                'integrated_density': True,
            },
            'cell_count': {
                'min_size': 10,
                'max_size': 500,
                'circularity': (0.5, 1.0),
                'include_edges': False,
                'dark_background': False,
            },
            'wound_healing': {
                'threshold_method': 'otsu',
                'measure_width': True,
                'measure_area': True,
                'dark_background': False,
            },
            'western_blot': {
                'lane_count': None,
                'background_subtract': True,
                'normalize': True,
                'dark_background': True,
            },
            'colony_count': {
                'min_size': 50,
                'max_size': 5000,
                'threshold': 'auto',
                'dark_background': False,
            },
            'particle_analysis': {
                'min_size': 1,
                'max_size': 1000,
                'circularity': (0.0, 1.0),
                'dark_background': None,
            },
            'colocalization': {
                'method': 'pearson',
                'channels': ['red', 'green'],
            },
            '3d_analysis': {
                'method': 'volume',
            },
            'general': {
                'measure_area': True,
                'measure_mean': True,
                'measure_std': True,
                'measure_min': True,
                'measure_max': True,
            },
        }

        return params.get(mode, params['general'])


class ImageJAnalyzer:
    """ImageJ 智能分析器"""

    def __init__(self):
        """初始化分析器"""
        self.processor = get_processor()
        self.decision_engine = AnalysisDecision()
        self.calibration = get_calibration()
        log("ImageJ 分析器初始化完成")

    def analyze(self, image_path, task=None, mode=None, params=None):
        """
        智能分析图像

        Args:
            image_path: 图像路径
            task: 任务描述（用于自动选择模式）
            mode: 分析模式（如果提供则覆盖自动选择）
            params: 分析参数（可选）

        Returns:
            dict: 分析结果
        """
        image_path = str(Path(image_path).absolute())
        log(f"开始分析：{image_path}")

        # 决定分析模式
        if mode is None:
            if task:
                mode = self.decision_engine.decide_mode(task)
            else:
                mode = 'general'

        log(f"使用分析模式：{mode}")

        # 获取默认参数
        default_params = self.decision_engine.get_default_params(mode)
        if params:
            default_params.update(params)

        # 执行分析
        result = self._execute_analysis(image_path, mode, default_params)

        # 添加元数据
        result['image'] = image_path
        result['mode'] = mode
        result['timestamp'] = datetime.now().isoformat()
        result['parameters'] = default_params

        # 生成结论
        result['conclusion'] = self._generate_conclusion(result, mode)

        log(f"分析完成：{result.get('conclusion', '无结论')}")

        return result

    def _execute_analysis(self, image_path, mode, params):
        """执行具体分析"""
        img = self.processor.open(image_path)

        if mode == 'fluorescence':
            return self._analyze_fluorescence(img, params)
        elif mode == 'cell_count':
            return self._analyze_cell_count(img, params)
        elif mode == 'wound_healing':
            return self._analyze_wound_healing(img, params)
        elif mode == 'western_blot':
            return self._analyze_western_blot(img, params)
        elif mode == 'colony_count':
            return self._analyze_colony_count(img, params)
        elif mode == 'particle_analysis':
            return self._analyze_particles(img, params)
        elif mode == 'colocalization':
            return self._analyze_colocalization(img, params)
        elif mode == '3d_analysis':
            return self._analyze_3d(img, params)
        else:
            return self._analyze_general(img, params)

    def _analyze_fluorescence(self, img, params):
        """荧光强度分析（支持暗背景和 Integrated Density）"""
        log("执行荧光强度分析")

        dark_background = params.get('dark_background', True)

        if params.get('threshold') is not None:
            thresh_val = params.get('threshold')
        else:
            thresh_method = params.get('threshold_method', 'otsu')
            thresh_val = self.processor.get_auto_threshold(img, thresh_method)

        stats = self.processor.measure(img)

        if dark_background:
            binary = self.processor.threshold(img, thresh_val, 255, dark_background=True)
        else:
            binary = self.processor.threshold(img, thresh_val, 255, dark_background=False)

        positive_results = self.processor.analyze_particles(binary)

        positive_area = positive_results.get('total_area', 0)
        if positive_area > 0:
            integrated_density = positive_area * stats['mean']
        else:
            integrated_density = stats.get('integrated_density', stats.get('mean', 0) * stats.get('area', 1))

        return {
            'mean_intensity': stats.get('mean', 0),
            'std_intensity': stats.get('std_dev', 0),
            'min_intensity': stats.get('min', 0),
            'max_intensity': stats.get('max', 0),
            'integrated_density': integrated_density,
            'positive_area': positive_area,
            'positive_area_ratio': positive_area / max(stats.get('area', 1), 1),
            'positive_cells': positive_results.get('count', 0),
            'threshold_used': thresh_val,
            'threshold_method': thresh_method,
            'dark_background': dark_background,
        }

    def _analyze_cell_count(self, img, params):
        """细胞计数分析"""
        log("执行细胞计数分析")

        enhanced = self.processor.enhance_contrast(img, params.get('saturation', 0.35))

        if params.get('threshold') is not None:
            thresh_val = params.get('threshold')
        else:
            thresh_method = params.get('threshold_method', 'otsu')
            thresh_val = self.processor.get_auto_threshold(enhanced, thresh_method)

        binary = self.processor.threshold(enhanced, thresh_val, 255, dark_background=False)

        results = self.processor.analyze_particles(
            binary,
            min_size=params.get('min_size', 10),
            max_size=params.get('max_size', 500)
        )

        areas = results.get('areas', [1])
        return {
            'total_cells': results.get('count', 0),
            'mean_area': sum(areas) / max(len(areas), 1),
            'cell_sizes': results.get('areas', []),
            'centroids': results.get('centroids', []),
            'density': results.get('count', 0) / 1000,
            'threshold_used': thresh_val,
        }

    def _analyze_wound_healing(self, img, params):
        """伤口愈合分析"""
        log("执行伤口愈合分析")

        results = self.processor.analyze_wound(
            img,
            method=params.get('method', 'edge_detection')
        )

        return {
            'wound_area': results.get('wound_area', 0),
            'wound_width': results.get('wound_width', 0),
            'healing_rate': results.get('healing_rate', 0),
        }

    def _analyze_western_blot(self, img, params):
        """Western Blot 分析"""
        log("执行 Western Blot 分析")

        results = self.processor.analyze_western_blot(
            img,
            lane_count=params.get('lane_count'),
            background_subtract=params.get('background_subtract', True),
            rolling_ball=params.get('rolling_ball', 50.0)
        )

        return results

    def _analyze_colony_count(self, img, params):
        """菌落计数分析"""
        log("执行菌落计数分析")

        if params.get('threshold') is not None:
            thresh_val = params.get('threshold')
        else:
            thresh_method = params.get('threshold_method', 'otsu')
            thresh_val = self.processor.get_auto_threshold(img, thresh_method)

        binary = self.processor.threshold(img, thresh_val, 255, dark_background=False)

        results = self.processor.analyze_particles(
            binary,
            min_size=params.get('min_size', 50),
            max_size=params.get('max_size', 5000)
        )

        areas = results.get('areas', [1])
        return {
            'colony_count': results.get('count', 0),
            'mean_size': sum(areas) / max(len(areas), 1),
            'size_distribution': results.get('areas', []),
        }

    def _analyze_particles(self, img, params):
        """颗粒分析"""
        log("执行颗粒分析")

        dark_background = params.get('dark_background', None)

        if params.get('threshold') is not None:
            thresh_val = params.get('threshold')
        else:
            thresh_method = params.get('threshold_method', 'otsu')
            thresh_val = self.processor.get_auto_threshold(img, thresh_method)

        # 自动检测背景类型
        if dark_background is None:
            h, w = img.shape[:2]
            center_region = img[h//4:3*h//4, w//4:3*w//4]
            if np.mean(center_region) < np.mean(img) * 0.8:
                dark_background = True
            else:
                dark_background = False

        binary = self.processor.threshold(img, thresh_val=thresh_val, dark_background=dark_background)

        results = self.processor.analyze_particles(
            binary,
            min_size=params.get('min_size', 1),
            max_size=params.get('max_size', 1000)
        )

        areas = results.get('areas', [1])
        return {
            'particle_count': results.get('count', 0),
            'mean_size': sum(areas) / max(len(areas), 1),
            'size_distribution': results.get('areas', []),
            'threshold_used': thresh_val,
            'dark_background': dark_background,
        }

    def _analyze_colocalization(self, img, params):
        """共定位分析（新增）"""
        log("执行共定位分析")

        channels = self.processor.split_channels(img)

        ch1_name = params.get('channel1', 'red')
        ch2_name = params.get('channel2', 'green')

        ch1 = channels.get(ch1_name)
        ch2 = channels.get(ch2_name)

        if ch1 is None or ch2 is None:
            return {
                'error': f'Channels {ch1_name} and/or {ch2_name} not found',
                'available_channels': list(channels.keys())
            }

        method = params.get('method', 'pearson')
        results = self.processor.colocalization(ch1, ch2, method=method)

        return {
            'channel1': ch1_name,
            'channel2': ch2_name,
            **results
        }

    def _analyze_3d(self, img, params):
        """3D 分析（新增）"""
        log("执行 3D 分析")

        if img.ndim == 2:
            # 2D image, treat as single slice
            return {
                'error': '3D analysis requires a stack of images',
                'note': 'Please provide a multi-slice TIFF or image stack'
            }

        method = params.get('method', 'volume')

        # Simple 3D analysis
        volume = np.sum(img > np.mean(img))
        surface_area = 0
        if img.ndim == 3:
            # Estimate surface area
            from scipy import ndimage
            binary = img > np.mean(img)
            surface_area = float(np.sum(ndimage.sobel(binary)))

        return {
            'method': method,
            'volume': int(volume),
            'surface_area': surface_area,
            'shape': list(img.shape),
        }

    def _analyze_general(self, img, params):
        """通用分析"""
        log("执行通用分析")

        stats = self.processor.measure(img)

        return {
            'mean_intensity': stats.get('mean', 0),
            'std_intensity': stats.get('std_dev', 0),
            'min_intensity': stats.get('min', 0),
            'max_intensity': stats.get('max', 0),
            'total_area': stats.get('area', 0),
        }

    def _generate_conclusion(self, result, mode):
        """生成分析结论"""
        if mode == 'fluorescence':
            mean = result.get('mean_intensity', 0)
            if mean > 200:
                return "荧光强度很强"
            elif mean > 100:
                return "荧光强度中等"
            else:
                return "荧光强度较弱"

        elif mode == 'cell_count':
            count = result.get('total_cells', 0)
            if count > 500:
                return "细胞密度很高"
            elif count > 100:
                return "细胞密度正常"
            else:
                return "细胞密度较低"

        elif mode == 'wound_healing':
            rate = result.get('healing_rate', 0)
            return f"伤口愈合率 {rate:.1%}"

        elif mode == 'colony_count':
            count = result.get('colony_count', 0)
            return f"检测到 {count} 个菌落"

        elif mode == 'particle_analysis':
            count = result.get('particle_count', 0)
            return f"检测到 {count} 个颗粒"

        elif mode == 'colocalization':
            pearson = result.get('pearson_coefficient', 0)
            if pearson > 0.7:
                return f"强共定位 (Pearson={pearson:.2f})"
            elif pearson > 0.3:
                return f"中等共定位 (Pearson={pearson:.2f})"
            else:
                return f"弱共定位 (Pearson={pearson:.2f})"

        elif mode == 'western_blot':
            lanes = result.get('lane_count', 0)
            return f"检测到 {lanes} 个泳道"

        elif mode == '3d_analysis':
            volume = result.get('volume', 0)
            return f"3D 体积分析完成，总体积：{volume}"

        else:
            return f"分析完成，平均强度：{result.get('mean_intensity', 0):.1f}"

    def batch_analyze(self, image_paths, mode='general', params=None, output_dir=None):
        """批量分析"""
        results = []

        for image_path in image_paths:
            try:
                result = self.analyze(image_path, mode=mode, params=params)
                results.append(result)

                if output_dir:
                    output_path = Path(output_dir) / (Path(image_path).stem + '_result.json')
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(to_python_type(result), f, indent=2, ensure_ascii=False)
            except Exception as e:
                log(f"分析失败 {image_path}: {e}")
                results.append({
                    'image': image_path,
                    'error': str(e)
                })

        return results


# ==================== 快捷函数 ====================

_analyzer = None

def get_analyzer():
    """获取分析器实例"""
    global _analyzer
    if _analyzer is None:
        _analyzer = ImageJAnalyzer()
    return _analyzer

def analyze_image(image_path, task=None, mode=None, params=None):
    """快捷分析函数"""
    analyzer = get_analyzer()
    return analyzer.analyze(image_path, task, mode, params)

def batch_analyze_images(image_paths, mode='general', params=None, output_dir=None):
    """快捷批量分析函数"""
    analyzer = get_analyzer()
    return analyzer.batch_analyze(image_paths, mode, params, output_dir)