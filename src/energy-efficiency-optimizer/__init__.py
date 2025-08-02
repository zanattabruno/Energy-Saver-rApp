"""
Energy Efficiency Optimizer Package

This package contains optimization algorithms and models for energy-efficient
resource allocation in wireless networks.
"""

# Make the optimal_model subpackage available
from . import optimal_model
from . import heuristic_model

__all__ = ['optimal_model', 'heuristic_model']
