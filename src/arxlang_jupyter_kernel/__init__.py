"""
title: Top-level package for arxlang-jupyter-kernel.
"""

from .kernel import ArxKernel

__all__ = ["ArxKernel", "__version__"]
__version__ = "0.1.2"  # semantic-release
