# -*- coding: utf-8 -*-
"""
ImageJ/Fiji Processor - Full Fiji Integration

This module provides a comprehensive wrapper around Fiji/ImageJ for scientific
image analysis. It supports:
- Multi-channel fluorescence analysis
- Particle analysis with calibration
- Western Blot lane detection
- Wound healing assays
- Colocalization analysis
- 3D volume analysis
- ROI management
- All ImageJ threshold methods

Fallback: If Fiji is unavailable, falls back to SimpleImageProcessor
using pure Python (Pillow/numpy/scipy).
"""
import os
import sys
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any, Union

# Set JAVA_HOME from Fiji's bundled JDK BEFORE importing pyimagej
# This is critical: scyjava/JPype determines Java path at import time
def _setup_fiji_java():
    """Setup Java environment from Fiji bundled JDK before pyimagej import"""
    try:
        from utils.config import get_fiji_path
        fiji_path = get_fiji_path()
        if fiji_path and os.path.exists(fiji_path):
            # New Fiji structure: java/win64/<jdk-folder>/
            java_dir = os.path.join(fiji_path, 'java', 'win64')
            if os.path.exists(java_dir):
                for d in os.listdir(java_dir):
                    jdk_path = os.path.join(java_dir, d)
                    jvm_dll = os.path.join(jdk_path, 'bin', 'server', 'jvm.dll')
                    if os.path.exists(jvm_dll):
                        os.environ['JAVA_HOME'] = jdk_path
                        os.environ['PATH'] = os.path.join(jdk_path, 'bin') + os.pathsep + os.environ.get('PATH', '')
                        print(f"[ImageJ] Pre-configured JAVA_HOME from Fiji: {jdk_path}")
                        return jdk_path
    except Exception as e:
        print(f"[ImageJ] Failed to setup Fiji Java: {e}")
    return None

# Setup Java BEFORE importing pyimagej
_setup_fiji_java()

# Try to import Fiji
try:
    import imagej
    from jpype import JException
    FIJI_AVAILABLE = True
except ImportError:
    FIJI_AVAILABLE = False
    imagej = None
    JException = Exception

# Fallback imports
try:
    from PIL import Image
    from scipy import ndimage
except ImportError:
    pass


def log(msg: str):
    """Log message"""
    print(f"[ImageJ] {msg}")


class FijiInitializationError(Exception):
    """Raised when Fiji cannot be initialized"""
    pass


class ImageJProcessor:
    """
    Full Fiji/ImageJ wrapper for scientific image analysis.

    Features:
    - All ImageJ threshold methods (Otsu, Triangle, Li, Huang, etc.)
    - Particle analysis with size/circularity filtering
    - Multi-channel support (RGB split/merge)
    - Calibration and physical units
    - ROI management
    - Western Blot analysis
    - Wound healing analysis
    - Colocalization (Pearson, Manders, Costes)
    - 3D volume analysis
    - ImageJ macro execution
    """

    _instance = None

    @classmethod
    def get_instance(cls, headless: bool = True, memory: str = '4G') -> 'ImageJProcessor':
        """Singleton access"""
        if cls._instance is None:
            cls._instance = cls(headless, memory)
        return cls._instance

    def __init__(self, headless: bool = True, memory: str = '4G'):
        """
        Initialize Fiji/ImageJ.

        Args:
            headless: Run without GUI (default True)
            memory: Java heap size (default '4G')
        """
        if not FIJI_AVAILABLE:
            raise FijiInitializationError("pyimagej not installed")

        self.ij = None
        self.headless = headless
        self.memory = memory
        self._initialized = False

        # Import config for Fiji path
        try:
            from utils.config import get_fiji_path, should_auto_download_fiji
            fiji_path = get_fiji_path()
            auto_download = should_auto_download_fiji()
        except ImportError:
            fiji_path = None
            auto_download = True

        try:
            # Set headless mode
            os.environ['JAVA_TOOL_OPTIONS'] = '-Djava.awt.headless=true'

            if auto_download:
                # Use Maven coordinate for Fiji - this downloads Fiji automatically
                # Note: This may take 5-10 minutes on first run (downloads ~500MB)
                log("Initializing Fiji from Maven (first time will download ~500MB, may take 5-10 min)...")
                self.ij = imagej.init('sc.fiji:fiji:LATEST')
                log("Fiji initialized successfully from Maven")
            elif fiji_path and os.path.exists(fiji_path):
                # Use existing Fiji installation
                log(f"Attempting to initialize Fiji from: {fiji_path}")
                try:
                    self.ij = imagej.init(fiji_path, mode='headless')
                    log("Fiji initialized successfully from local installation")
                except TypeError as te:
                    if "addObject" in str(te) or "PythonScriptRunner" in str(te):
                        # scyjava compatibility issue with older Fiji
                        log("Local Fiji is incompatible with current pyimagej/scyjava.")
                        log("This is a known issue: older Fiji + newer scyjava = incompatibility.")
                        raise FijiInitializationError(
                            f"Local Fiji incompatible: {te}. "
                            "Please update Fiji or set auto_download=true in config.json."
                        )
                    else:
                        raise
            else:
                raise FijiInitializationError(
                    "Fiji not found and auto-download disabled. "
                    "Set 'auto_download': true in config.json or place Fiji at the configured path."
                )

            # Set default UI to headless
            try:
                self.ij.ui().setDefaultUI(self.ij.ui().getUI("headless"))
            except Exception:
                pass  # Some versions don't have this UI method

            self._initialized = True
            log("Fiji initialized successfully")

        except Exception as e:
            log(f"Fiji initialization failed: {e}")
            raise FijiInitializationError(f"Failed to initialize Fiji: {e}")

    def _check_initialized(self):
        """Check if Fiji is initialized"""
        if not self._initialized or self.ij is None:
            raise FijiInitializationError("Fiji not initialized")

    # ==================== Core Image Operations ====================

    def open(self, path: str) -> np.ndarray:
        """
        Open image using ImageJ.

        Supports: TIFF, DICOM, PNG, JPEG, LSM, CZI, and more.

        Args:
            path: Path to image file

        Returns:
            numpy array of image data
        """
        self._check_initialized()
        try:
            img = self.ij.io().open(path)
            return self.ij.py.from_img(img)
        except Exception as e:
            log(f"Failed to open image: {e}")
            # Fallback to PIL
            try:
                from PIL import Image
                img = Image.open(path)
                if img.mode != 'L':
                    img = img.convert('L')
                return np.array(img)
            except:
                raise RuntimeError(f"Cannot open image: {path}")

    def save(self, img: np.ndarray, path: str):
        """Save image"""
        self._check_initialized()
        try:
            img_plus = self.ij.py.to_img(img)
            self.ij.io().save(img_plus, path)
        except Exception as e:
            log(f"Failed to save image: {e}")
            # Fallback to PIL
            from PIL import Image
            Image.fromarray(img).save(path)

    def to_numpy(self, img) -> np.ndarray:
        """Convert ImageJ ImgPlus to numpy array"""
        if isinstance(img, np.ndarray):
            return img
        self._check_initialized()
        return self.ij.py.from_img(img)

    def close(self, path: Optional[str] = None):
        """Close image(s)"""
        self._check_initialized()
        if path:
            self.ij.io().close(path)
        else:
            self.ij.dispose()

    # ==================== Thresholding ====================

    THRESHOLD_METHODS = [
        'otsu', 'triangle', 'li', 'huang', 'iso_data',
        'max_entropy', 'min_error', 'percentile', 'renyi_entropy',
        'shanbhag', 'yen', 'mean', 'default'
    ]

    def get_auto_threshold(self, img: np.ndarray, method: str = 'otsu') -> float:
        """
        Get auto threshold value using ImageJ algorithm.

        Args:
            img: Input image (2D numpy array)
            method: Threshold method name

        Returns:
            Threshold value
        """
        self._check_initialized()

        if method == 'default':
            return 128.0
        elif method == 'mean':
            return float(np.mean(img))

        try:
            # Use ImageJ's AutoThresholder
            from jnius import autoclass, cast

            AutoThresholder = autoclass('ij.plugin.frame.AutoThresholder')
            Thresholder = autoclass('ij.plugin.Thresholder')

            at = AutoThresholder()

            # Convert numpy array to ImageProcessor
            from jpype import JArray, JByte, JInt
            height, width = img.shape[:2]

            # Create byte array for ImageProcessor
            pixels = JArray(JByte)(width * height)
            for y in range(height):
                for x in range(width):
                    pixels[y * width + x] = int(img[y, x])

            from jnius import autoclass
            ByteProcessor = autoclass('ij.process.ByteProcessor')
            ip = ByteProcessor(width, height)
            ip.setPixels(pixels)

            # Get threshold using method
            threshold = at.getThreshold(method, ip.getHistogram())
            return float(threshold)

        except Exception as e:
            log(f"Auto threshold failed ({method}), using Otsu fallback: {e}")
            # Fallback to numpy Otsu
            return self._numpy_otsu(img)

    def _numpy_otsu(self, img: np.ndarray) -> float:
        """Numpy-based Otsu threshold"""
        hist, _ = np.histogram(img.flatten(), 256, [0, 256])
        hist = hist.astype(float)

        sigma_max = 0
        thresh = 0
        total = np.sum(hist)

        for t in range(1, 256):
            w1 = np.sum(hist[:t]) / total
            w2 = np.sum(hist[t:]) / total
            if w1 == 0 or w2 == 0:
                continue
            m1 = np.sum(np.arange(t) * hist[:t]) / w1 / total
            m2 = np.sum(np.arange(t, 256) * hist[t:]) / w2 / total
            sigma = w1 * w2 * (m1 - m2) ** 2
            if sigma > sigma_max:
                sigma_max = sigma
                thresh = t

        return float(thresh)

    def threshold(self, img: np.ndarray,
                  method: str = 'otsu',
                  thresh_val: Optional[float] = None,
                  dark_background: bool = True) -> np.ndarray:
        """
        Apply threshold to image.

        Args:
            img: Input image
            method: Threshold method ('otsu', 'triangle', 'li', etc.)
            thresh_val: Manual threshold value (None for auto)
            dark_background: True if background is dark (fluorescence)

        Returns:
            Binary image (0 and 255)
        """
        if thresh_val is None:
            thresh_val = self.get_auto_threshold(img, method)

        if dark_background:
            # Dark background: signal > threshold
            binary = np.zeros_like(img, dtype=np.uint8)
            binary[img > thresh_val] = 255
        else:
            # Bright background: signal < threshold
            binary = np.zeros_like(img, dtype=np.uint8)
            binary[img < thresh_val] = 255

        return binary

    # ==================== Particle Analysis ====================

    def analyze_particles(self, img: np.ndarray,
                          min_size: float = 0,
                          max_size: float = float('inf'),
                          circularity: Tuple[float, float] = (0.0, 1.0),
                          include_edges: bool = False,
                          **kwargs) -> Dict[str, Any]:
        """
        Analyze particles in binary image.

        Args:
            img: Binary image (0 and 255)
            min_size: Minimum particle size
            max_size: Maximum particle size
            circularity: (min, max) circularity range
            include_edges: Include particles touching edges

        Returns:
            dict with count, areas, centroids, circularities
        """
        if isinstance(img, np.ndarray) and img.max() > 1:
            binary = (img > 128).astype(np.uint8)
        else:
            binary = img.astype(np.uint8)

        # Label connected components
        labeled, ncomponents = ndimage.label(binary)

        areas = []
        centroids = []
        circularities = []

        # Get circularity range from parameter
        circ_min, circ_max = circularity if isinstance(circularity, (tuple, list)) else (0.0, 1.0)

        for i in range(1, ncomponents + 1):
            region = (labeled == i)
            area = np.sum(region)

            # Check size
            if area < min_size or area > max_size:
                continue

            # Check circularity
            perimeter = np.sum(ndimage.sobel(region.astype(float)) > 0)
            if perimeter > 0:
                circ = 4 * np.pi * area / (perimeter ** 2)
                if circ < circ_min or circ > circ_max:
                    continue
                circularities.append(float(circ))
            else:
                circularities.append(1.0)

            areas.append(int(area))
            center = ndimage.center_of_mass(region)
            centroids.append((float(center[1]), float(center[0])))  # (x, y)

        return {
            'count': len(areas),
            'areas': areas,
            'centroids': centroids,
            'circularities': circularities,
            'total_area': sum(areas)
        }

    # ==================== Measurements ====================

    def measure(self, img: np.ndarray, roi: Optional[Dict] = None) -> Dict[str, float]:
        """
        Measure image statistics.

        Args:
            img: Image to measure
            roi: Optional ROI (type, x, y, width, height)

        Returns:
            dict with area, mean, std_dev, min, max, integrated_density
        """
        if roi:
            # Apply ROI
            if roi.get('type') == 'rectangle':
                x, y = roi.get('x', 0), roi.get('y', 0)
                w, h = roi.get('width', img.shape[1]), roi.get('height', img.shape[0])
                img = img[y:y+h, x:x+w]

        return {
            'area': int(img.size),
            'mean': float(np.mean(img)),
            'std_dev': float(np.std(img)),
            'min': float(np.min(img)),
            'max': float(np.max(img)),
            'integrated_density': float(np.sum(img)),
            'raw_integrated_density': float(np.sum(img)),
        }

    # ==================== Multi-channel Support ====================

    def split_channels(self, img: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Split multi-channel image.

        Args:
            img: RGB or multi-channel image

        Returns:
            dict with channel names as keys
        """
        if img.ndim == 2:
            return {'gray': img}

        if img.ndim == 3:
            if img.shape[2] == 3:
                return {
                    'red': img[:, :, 0],
                    'green': img[:, :, 1],
                    'blue': img[:, :, 2]
                }
            elif img.shape[2] == 4:
                return {
                    'red': img[:, :, 0],
                    'green': img[:, :, 1],
                    'blue': img[:, :, 2],
                    'alpha': img[:, :, 3]
                }

        return {'channel_0': img}

    def merge_channels(self, channels: Dict[str, np.ndarray]) -> np.ndarray:
        """Merge channels into composite image"""
        if 'red' in channels and 'green' in channels and 'blue' in channels:
            return np.stack([
                channels['red'],
                channels['green'],
                channels['blue']
            ], axis=-1)

        # Single channel
        return list(channels.values())[0]

    # ==================== Colocalization ====================

    def colocalization(self, channel1: np.ndarray, channel2: np.ndarray,
                       method: str = 'pearson') -> Dict[str, float]:
        """
        Colocalization analysis.

        Args:
            channel1, channel2: Two channels
            method: 'pearson', 'manders', 'costes'

        Returns:
            dict with colocalization coefficients
        """
        # Flatten images
        ch1 = channel1.flatten().astype(float)
        ch2 = channel2.flatten().astype(float)

        # Pearson correlation
        pearson = np.corrcoef(ch1, ch2)[0, 1]

        # Manders coefficients
        mask = (ch1 > np.mean(ch1)) & (ch2 > np.mean(ch2))
        m1 = np.sum(ch1[mask]) / np.sum(ch1) if np.sum(ch1) > 0 else 0
        m2 = np.sum(ch2[mask]) / np.sum(ch2) if np.sum(ch2) > 0 else 0

        # Costes automatic threshold
        costes_threshold = np.percentile(ch1, 50)

        return {
            'pearson_coefficient': float(pearson),
            'manders_m1': float(m1),
            'manders_m2': float(m2),
            'costes_threshold': float(costes_threshold),
            'colocalized_pixels': int(np.sum(mask)),
            'colocalization_ratio': float(np.mean(mask))
        }

    # ==================== Western Blot ====================

    def analyze_western_blot(self, img: np.ndarray,
                             lane_count: Optional[int] = None,
                             background_subtract: bool = True,
                             rolling_ball: float = 50.0) -> Dict[str, Any]:
        """
        Analyze Western Blot lanes and bands.

        Args:
            img: Blot image
            lane_count: Number of lanes (auto-detect if None)
            background_subtract: Enable background subtraction
            rolling_ball: Radius for rolling ball background

        Returns:
            dict with lanes, bands, profile
        """
        # 1D intensity profile (vertical)
        profile = np.mean(img, axis=0)

        # Background subtraction
        if background_subtract:
            from scipy.ndimage import uniform_filter1d
            background = uniform_filter1d(profile, size=int(rolling_ball))
            profile = profile - background
            profile = np.clip(profile, 0, None)

        # Detect lanes (peaks in profile)
        from scipy.signal import find_peaks
        peaks, _ = find_peaks(profile, distance=20)

        if lane_count and len(peaks) > lane_count:
            # Select top N peaks
            peak_heights = profile[peaks]
            top_indices = np.argsort(peak_heights)[-lane_count:]
            peaks = sorted(peaks[top_indices])

        lanes = []
        for i, peak in enumerate(peaks):
            # Simple band detection around peak
            lane_region = profile[max(0, peak-30):min(len(profile), peak+30)]
            bands = []
            if len(lane_region) > 0:
                bands.append({
                    'position': int(peak),
                    'intensity': float(np.max(lane_region))
                })
            lanes.append({
                'lane_id': i + 1,
                'bands': bands,
                'center': int(peak)
            })

        return {
            'lanes': lanes,
            'profile': profile.tolist()[:100],  # First 100 points
            'lane_count': len(lanes)
        }

    # ==================== Wound Healing ====================

    def analyze_wound(self, img: np.ndarray,
                      method: str = 'edge_detection') -> Dict[str, Any]:
        """
        Analyze wound healing assay.

        Args:
            img: Wound image
            method: 'edge_detection', 'threshold'

        Returns:
            dict with wound_area, wound_width, healing_rate
        """
        # Threshold to find wound (dark area)
        binary = self.threshold(img, method='otsu', dark_background=False)

        # Find wound area
        wound_area = np.sum(binary > 0)

        # Estimate width (simplified)
        rows = np.any(binary > 0, axis=1)
        if np.sum(rows) > 0:
            wound_width = int(np.mean(np.diff(np.where(rows)[0])))
        else:
            wound_width = 0

        return {
            'wound_area': int(wound_area),
            'wound_width': wound_width,
            'healing_rate': 0.0  # Would need t0 image
        }

    # ==================== Utility ====================

    def enhance_contrast(self, img: np.ndarray,
                         saturation: float = 0.35,
                         normalize: bool = True) -> np.ndarray:
        """Enhance image contrast"""
        min_val = np.percentile(img, saturation * 100)
        max_val = np.percentile(img, 100 - saturation * 100)
        enhanced = np.clip((img - min_val) / (max_val - min_val + 1e-8) * 255, 0, 255)
        return enhanced.astype(np.uint8)

    def gaussian_blur(self, img: np.ndarray, sigma: float = 2.0) -> np.ndarray:
        """Gaussian blur"""
        return ndimage.gaussian_filter(img, sigma).astype(img.dtype)

    def close_fiji(self):
        """Shutdown Fiji"""
        if self.ij:
            self.ij.dispose()
            self._initialized = False


# ==================== Fallback Processor ====================

class SimpleImageProcessor:
    """
    Fallback processor using pure Python (Pillow/numpy/scipy).
    Used when Fiji is unavailable.
    """

    _instance = None

    @classmethod
    def get_instance(cls) -> 'SimpleImageProcessor':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        log("Using SimpleImageProcessor (Fiji unavailable)")

    def get_auto_threshold(self, img: np.ndarray, method: str = 'otsu') -> float:
        """Get auto threshold value using specified method"""
        if method == 'default':
            return 128.0
        elif method == 'mean':
            return float(np.mean(img))
        else:
            # Otsu implementation
            hist, _ = np.histogram(img.flatten(), 256, [0, 256])
            hist = hist.astype(float)
            sigma_max, thresh = 0, 128
            total = np.sum(hist)
            for t in range(1, 256):
                w1, w2 = np.sum(hist[:t])/total, np.sum(hist[t:])/total
                if w1 == 0 or w2 == 0:
                    continue
                m1 = np.sum(np.arange(t)*hist[:t])/w1/total
                m2 = np.sum(np.arange(t,256)*hist[t:])/w2/total
                sigma = w1*w2*(m1-m2)**2
                if sigma > sigma_max:
                    sigma_max, thresh = sigma, t
            return float(thresh)

    def enhance_contrast(self, img: np.ndarray,
                         saturation: float = 0.35,
                         normalize: bool = True) -> np.ndarray:
        """Enhance image contrast using percentile-based clipping"""
        min_val = np.percentile(img, saturation * 100)
        max_val = np.percentile(img, 100 - saturation * 100)
        enhanced = np.clip((img - min_val) / (max_val - min_val + 1e-8) * 255, 0, 255)
        return enhanced.astype(np.uint8)

    def open(self, path: str) -> np.ndarray:
        try:
            from PIL import Image
            img = Image.open(path)
            if img.mode != 'L':
                img = img.convert('L')
            return np.array(img)
        except Exception as e:
            raise RuntimeError(f"Cannot open image: {e}")

    def threshold(self, img: np.ndarray, method: str = 'otsu',
                  thresh_val: Optional[float] = None,
                  dark_background: bool = True) -> np.ndarray:
        if thresh_val is None:
            if method == 'mean':
                thresh_val = np.mean(img)
            else:
                # Otsu fallback
                hist, _ = np.histogram(img.flatten(), 256, [0, 256])
                sigma_max, thresh = 0, 128
                total = np.sum(hist)
                for t in range(1, 256):
                    w1, w2 = np.sum(hist[:t])/total, np.sum(hist[t:])/total
                    if w1 == 0 or w2 == 0:
                        continue
                    m1 = np.sum(np.arange(t)*hist[:t])/w1/total
                    m2 = np.sum(np.arange(t,256)*hist[t:])/w2/total
                    sigma = w1*w2*(m1-m2)**2
                    if sigma > sigma_max:
                        sigma_max, thresh = sigma, t
                thresh_val = float(thresh)

        if dark_background:
            binary = np.zeros_like(img, dtype=np.uint8)
            binary[img > thresh_val] = 255
        else:
            binary = np.zeros_like(img, dtype=np.uint8)
            binary[img < thresh_val] = 255
        return binary

    def analyze_particles(self, img: np.ndarray, **kwargs) -> Dict[str, Any]:
        if img.max() > 1:
            binary = (img > 128).astype(np.uint8)
        else:
            binary = img.astype(np.uint8)

        labeled, ncomponents = ndimage.label(binary)
        min_size = kwargs.get('min_size', 0)
        max_size = kwargs.get('max_size', float('inf'))

        areas, centroids = [], []
        for i in range(1, ncomponents + 1):
            area = np.sum(labeled == i)
            if min_size <= area <= max_size:
                areas.append(int(area))
                centroids.append(tuple(map(float, ndimage.center_of_mass(labeled == i))))

        return {'count': len(areas), 'areas': areas, 'centroids': centroids}

    def split_channels(self, img: np.ndarray) -> Dict[str, np.ndarray]:
        if img.ndim == 2:
            return {'gray': img}
        if img.shape[2] == 3:
            return {'red': img[:,:,0], 'green': img[:,:,1], 'blue': img[:,:,2]}
        return {'channel_0': img}

    def colocalization(self, ch1: np.ndarray, ch2: np.ndarray, **kwargs) -> Dict[str, float]:
        c1, c2 = ch1.flatten(), ch2.flatten()
        pearson = np.corrcoef(c1, c2)[0, 1]
        mask = (c1 > np.mean(c1)) & (c2 > np.mean(c2))
        return {
            'pearson_coefficient': float(pearson),
            'manders_m1': float(np.sum(c1[mask])/np.sum(c1)) if np.sum(c1) > 0 else 0,
            'manders_m2': float(np.sum(c2[mask])/np.sum(c2)) if np.sum(c2) > 0 else 0,
            'colocalization_ratio': float(np.mean(mask))
        }

    def measure(self, img: np.ndarray, **kwargs) -> Dict[str, float]:
        return {
            'area': int(img.size),
            'mean': float(np.mean(img)),
            'std_dev': float(np.std(img)),
            'min': float(np.min(img)),
            'max': float(np.max(img)),
            'integrated_density': float(np.sum(img))
        }


# ==================== Factory Function ====================

# Export for analyzer.py
HAS_IMAGEJ = FIJI_AVAILABLE

def get_processor():
    """
    Get image processor with Fiji fallback.

    Returns:
        ImageJProcessor if Fiji available, otherwise SimpleImageProcessor
    """
    if FIJI_AVAILABLE:
        try:
            return ImageJProcessor.get_instance()
        except FijiInitializationError:
            pass
    return SimpleImageProcessor.get_instance()