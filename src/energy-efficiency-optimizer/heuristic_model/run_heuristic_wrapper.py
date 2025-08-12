"""
Wrapper module to make heuristic-model compatible with the main application.

This wrapper provides the run_heuristic_optimization function expected by the main application
while using the heuristic-model implementation internally.
"""

import random
import math
import json
import os
import sys
import traceback
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

# Import the heuristic model using absolute imports
from heuristic import run_heuristic
from classes import UE, E2_Node

# Import shared configuration and helpers
from optimization_config import OptimizationConfig, OptimizationHelpers, OptimizationWrapper


class HeuristicOptimizationHelpers(OptimizationHelpers):
    """Helper functions specific to heuristic optimization."""
    
    @staticmethod
    def precompute_imsi_measurements(input_json: Dict[str, Any]) -> Dict[str, Dict[tuple, float]]:
        """Precompute mapping IMSI -> {(nodebid, pci): sinr} for O(1) lookups.

        This avoids rescanning the entire input list for each IMSI and reduces
        complexity from O(N_unique_imsi * N_total) to O(N_total).
        """
        imsi_to_measurements: Dict[str, Dict[tuple, float]] = {}
        for u in input_json.get("users", []):
            imsi = u.get("IMSI")
            nodebid = u.get("nodebid")
            pci = u.get("pci")
            sinr = u.get("sinr")
            if imsi is None or nodebid is None or pci is None or sinr is None:
                continue
            key = (nodebid, pci)
            if imsi not in imsi_to_measurements:
                imsi_to_measurements[imsi] = {}
            # If duplicates exist, last one wins (or consider max/avg if needed)
            imsi_to_measurements[imsi][key] = sinr
        return imsi_to_measurements

    @staticmethod
    def build_heuristic_channel_gains(user_imsi: str, imsi_to_measurements: Dict[str, Dict[tuple, float]], 
                                     ID_to_nodebid_and_PCI: Dict[int, Tuple[str, int]]) -> Dict[int, float]:
        """Build channel gain mapping for heuristic model using precomputed measurements.

        Converts SINR (dB) to linear channel gains; applies a penalty for missing measurements.
        """
        channel_gains: Dict[int, float] = {}
        user_measurements = imsi_to_measurements.get(user_imsi, {})

        # Choose a baseline measurement for penalty; fallback to DEFAULT_POOR_SIGNAL
        baseline_sinr = next(iter(user_measurements.values()), OptimizationConfig.DEFAULT_POOR_SIGNAL)
        penalty_sinr = baseline_sinr - 10

        for e2n_id, (nodebid, pci) in ID_to_nodebid_and_PCI.items():
            sinr_db = user_measurements.get((nodebid, pci), penalty_sinr)
            channel_gains[e2n_id] = 10 ** (sinr_db / 10)
        return channel_gains
    
    @staticmethod
    def create_heuristic_users_dict(input_json: Dict[str, Any], 
                                   ID_to_nodebid_and_PCI: Dict[int, Tuple[str, int]]) -> Tuple[Dict[str, Any], Dict[str, int]]:
        """Create users dictionary for heuristic optimization (unique IMSIs only).

        Optimized to pre-index measurements and avoid repeated scans.
        """
        UEs = {"users": []}
        ID_to_IMSI: Dict[str, int] = {}
        user_id = 0

        # Precompute IMSI -> measurements map once
        imsi_to_measurements = HeuristicOptimizationHelpers.precompute_imsi_measurements(input_json)

        for imsi, measurements in imsi_to_measurements.items():
            ID_to_IMSI[imsi] = user_id
            channel_gains = HeuristicOptimizationHelpers.build_heuristic_channel_gains(
                imsi, imsi_to_measurements, ID_to_nodebid_and_PCI
            )
            demand = random.choice(OptimizationConfig.DEMANDS_PROFILE)

            UEs["users"].append({
                "ID": user_id,
                "demand": demand,
                "channel_gain": channel_gains
            })
            user_id += 1

        return UEs, ID_to_IMSI


class HeuristicOptimizationWrapper(OptimizationWrapper):
    """Wrapper for heuristic optimization model."""
    
    def __init__(self):
        """Initialize the heuristic optimization wrapper."""
        super().__init__()
        self.heuristic_helpers = HeuristicOptimizationHelpers()
    
    def run(self, input_json: Dict[str, Any]) -> Dict[str, Any]:
        """Run the heuristic optimization process."""
        try:
            print(f"Processing {len(input_json['users'])} users with heuristic optimization")
            
            # Extract E2 nodes and create mappings
            E2Ns, ID_to_nodebid_and_PCI = self.helpers.extract_unique_nodes(input_json)
            
            # Create users dictionary (using heuristic-specific method)
            UEs, ID_to_IMSI = self.heuristic_helpers.create_heuristic_users_dict(
                input_json, ID_to_nodebid_and_PCI
            )
            
            print(f"Created {len(E2Ns['E2_nodes'])} E2 nodes and {len(UEs['users'])} users for heuristic optimization")
            
            # Run the heuristic optimization
            total_bw = len(E2Ns["E2_nodes"]) * self.config.E2NS_BW
            connections, E2N_info, solution = run_heuristic(E2Ns, UEs, total_bw)
            
            # Format results using custom logic for heuristic
            result = self._format_heuristic_results(
                connections, E2N_info, ID_to_IMSI, ID_to_nodebid_and_PCI
            )
            
            print(f"Heuristic optimization completed: {len(result['Users admission'])} users admitted, "
                  f"{len(result['GNB_config'])} GNBs configured")
            
            return result
            
        except Exception as e:
            print(f"Heuristic optimization failed: {e}")
            traceback.print_exc()
            return {"Users admission": [], "GNB_config": []}
    
    def _format_heuristic_results(self, connections: Dict[int, int], E2N_info: Dict[int, Dict[str, Any]], 
                                 ID_to_IMSI: Dict[str, int], ID_to_nodebid_and_PCI: Dict[int, Tuple[str, int]]) -> Dict[str, Any]:
        """Format heuristic results with custom user admission logic."""
        # Build users admission list
        user_admissions = []
        for user_id, e2n_id in connections.items():
            if e2n_id in ID_to_nodebid_and_PCI:
                # Find the original IMSI for this user
                original_imsi = None
                for imsi, uid in ID_to_IMSI.items():
                    if uid == user_id:
                        original_imsi = imsi
                        break
                
                if original_imsi:
                    gnb_id, pci = ID_to_nodebid_and_PCI[e2n_id]
                    user_admissions.append({
                        "IMSI": original_imsi,
                        "gnb": gnb_id,
                        "pci": pci
                    })
        
        # Build GNB configurations
        gnb_configs = self.helpers.build_gnb_configurations(ID_to_nodebid_and_PCI, E2N_info)
        
        return {
            "Users admission": user_admissions,
            "GNB_config": gnb_configs
        }


def run_heuristic_optimization(input_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrapper function to make heuristic-model compatible with main application.
    
    Args:
        input_json (Dict): Input data in the format expected by main application
        
    Returns:
        Dict: Optimization results in the format expected by main application
    """
    wrapper = HeuristicOptimizationWrapper()
    return wrapper.run(input_json)


# For backward compatibility, also expose the original interface if needed
def run_heuristic_wrapper(E2Ns_dict, UEs_dict, total_BW=2500):
    """
    Direct wrapper for the run_heuristic function for advanced usage.
    
    Args:
        E2Ns_dict: E2 Nodes dictionary
        UEs_dict: Users dictionary  
        total_BW: Total bandwidth
        
    Returns:
        List: [connections, E2N_info, solution]
    """
    return run_heuristic(E2Ns_dict, UEs_dict, total_BW)
