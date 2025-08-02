"""
Wrapper module to make energy-efficiency-optimizer compatible with the main application.

This wrapper provides the run_optimization function expected by the main application
while using the energy-efficiency-optimizer implementation internally.
"""

import random
import math
import json
import tempfile
import os
import sys
from pathlib import Path
from typing import Dict, Any, Tuple

# Add current directory to path for absolute imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Add shared directory to path
shared_dir = os.path.join(os.path.dirname(current_dir), 'shared')
if shared_dir not in sys.path:
    sys.path.insert(0, shared_dir)

# Import the energy-efficiency-optimizer model using absolute imports
from model import run_model
from classes import UE, E2_Node

# Import shared configuration and helpers
from optimization_config import OptimizationConfig, OptimizationHelpers, OptimizationWrapper


class OptimalOptimizationWrapper(OptimizationWrapper):
    """Wrapper for optimal optimization model."""
    
    def run(self, input_json: Dict[str, Any]) -> Dict[str, Any]:
        """Run the optimal optimization process."""
        try:
            print(f"Processing {len(input_json['users'])} users with energy-efficiency-optimizer")
            
            # Extract E2 nodes and create mappings
            E2Ns, ID_to_nodebid_and_PCI = self.helpers.extract_unique_nodes(input_json)
            
            # Create users dictionary
            UEs, ID_to_IMSI = self.helpers.create_users_dict(input_json, ID_to_nodebid_and_PCI)
            
            # Run the optimization model
            total_bw = self.config.E2NS_BW * self.config.TOTAL_BW_MULTIPLIER
            connections, E2N_info, solution = run_model(E2Ns, UEs, total_bw)
            
            # Format and return results
            result = self.format_results(connections, E2N_info, ID_to_IMSI, ID_to_nodebid_and_PCI)
            
            print(f"Optimization completed: {len(result['Users admission'])} users admitted, "
                  f"{len(result['GNB_config'])} GNBs configured")
            
            return result
            
        except Exception as e:
            print(f"Energy-efficiency-optimizer failed: {e}")
            import traceback
            traceback.print_exc()
            return {"Users admission": [], "GNB_config": []}


def run_optimization(input_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrapper function to make energy-efficiency-optimizer compatible with main application.
    
    Args:
        input_json (Dict): Input data in the format expected by main application
        
    Returns:
        Dict: Optimization results in the format expected by main application
    """
    wrapper = OptimalOptimizationWrapper()
    return wrapper.run(input_json)


# For backward compatibility, also expose the original interface if needed
def run_model_wrapper(E2Ns_dict, UEs_dict, total_BW=2500):
    """
    Direct wrapper for the run_model function for advanced usage.
    
    Args:
        E2Ns_dict: E2 Nodes dictionary
        UEs_dict: Users dictionary  
        total_BW: Total bandwidth
        
    Returns:
        Tuple: (connections, E2N_info, solution)
    """
    return run_model(E2Ns_dict, UEs_dict, total_BW)
