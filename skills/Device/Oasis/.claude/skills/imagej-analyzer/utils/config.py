# -*- coding: utf-8 -*-
"""
Configuration module for ImageJ Analyzer Skill

Loads configuration from:
1. config.json file (with relative paths for portability)
2. Default values (fallback)

No environment variables used - all config is self-contained for easy skill portability.
"""
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

# Configuration file location
CONFIG_FILE = Path(__file__).parent / 'config.json'

# Default configuration
DEFAULT_CONFIG = {
    'fiji': {
        'path': None,
        'use_relative_path': True,
        'relative_path': '../Fiji.app',
        'memory': '4G',
        'headless': True,
        'auto_download': True
    },
    'analysis': {
        'default_threshold_method': 'otsu',
        'default_dark_background': True,
        'calibration': {
            'pixel_width': 1.0,
            'pixel_height': 1.0,
            'unit': 'pixel'
        }
    },
    'output': {
        'save_json': True,
        'save_images': False,
        'verbose': False
    }
}

# Cache for loaded config
_config_cache: Optional[Dict[str, Any]] = None


def load_config() -> Dict[str, Any]:
    """
    Load configuration from file.

    Returns:
        Configuration dictionary
    """
    global _config_cache

    if _config_cache is not None:
        return _config_cache

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                _config_cache = json.load(f)
        except Exception as e:
            print(f"Failed to load config: {e}, using defaults")
            _config_cache = DEFAULT_CONFIG.copy()
    else:
        _config_cache = DEFAULT_CONFIG.copy()

    return _config_cache


def save_config(config: Dict[str, Any]):
    """Save configuration to file"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    global _config_cache
    _config_cache = config


def get_fiji_path() -> Optional[str]:
    """
    Get Fiji path from config file.

    Uses relative path from skill directory for portability.

    Priority:
    1. Absolute path from config (if exists)
    2. Relative path from skill directory (default: ../Fiji.app)
    3. Auto-download via Maven (if enabled)

    Returns:
        Fiji path or None (None triggers auto-download)
    """
    config = load_config()
    fiji_config = config.get('fiji', {})

    # Check for absolute path first
    abs_path = fiji_config.get('path')
    if abs_path and os.path.exists(abs_path):
        return abs_path

    # Use relative path if enabled
    if fiji_config.get('use_relative_path', True):
        rel_path = fiji_config.get('relative_path', '../Fiji.app')
        # Resolve relative to skill directory (parent of utils/)
        skill_dir = CONFIG_FILE.parent.parent
        full_path = (skill_dir / rel_path).resolve()
        if full_path.exists():
            return str(full_path)

    return None


def get_fiji_memory() -> str:
    """Get Fiji memory setting from config"""
    config = load_config()
    return config.get('fiji', {}).get('memory', '4G')


def get_default_threshold_method() -> str:
    """Get default threshold method"""
    config = load_config()
    return config.get('analysis', {}).get('default_threshold_method', 'otsu')


def get_default_dark_background() -> bool:
    """Get default dark background setting"""
    config = load_config()
    return config.get('analysis', {}).get('default_dark_background', True)


def get_calibration() -> Dict[str, float]:
    """Get spatial calibration"""
    config = load_config()
    return config.get('analysis', {}).get('calibration', {
        'pixel_width': 1.0,
        'pixel_height': 1.0,
        'unit': 'pixel'
    })


def update_config(key_path: str, value: Any):
    """
    Update configuration value.

    Args:
        key_path: Dot-separated key path (e.g., 'fiji.memory')
        value: New value
    """
    config = load_config()

    keys = key_path.split('.')
    current = config
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    current[keys[-1]] = value
    save_config(config)


# Convenience functions for common operations
def is_fiji_headless() -> bool:
    """Check if Fiji should run in headless mode"""
    config = load_config()
    return config.get('fiji', {}).get('headless', True)


def should_auto_download_fiji() -> bool:
    """Check if Fiji should be auto-downloaded"""
    config = load_config()
    return config.get('fiji', {}).get('auto_download', True)


def use_relative_path() -> bool:
    """Check if relative path should be used"""
    config = load_config()
    return config.get('fiji', {}).get('use_relative_path', True)


def get_relative_fiji_path() -> str:
    """Get relative Fiji path setting"""
    config = load_config()
    return config.get('fiji', {}).get('relative_path', '../Fiji.app')