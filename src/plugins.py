import os
import importlib.util
import sys
from typing import Optional, Dict, Any
from pathlib import Path


def load_plugin(module_path: str, class_name: str, params: Optional[Dict[str, Any]] = None):
    parts = module_path.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid plugin module path '{module_path}'. Expected 'package.module'")

    package, module_name = parts
    spec = importlib.util.find_spec(package)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot find plugin module '{module_path}'. Is the package installed or in the Python path?")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_path] = module
    spec.loader.exec_module(module)

    if not hasattr(module, class_name):
        raise AttributeError(f"Plugin module '{module_path}' has no class '{class_name}'")

    cls = getattr(module, class_name)
    if params:
        return cls(**params)
    return cls()
