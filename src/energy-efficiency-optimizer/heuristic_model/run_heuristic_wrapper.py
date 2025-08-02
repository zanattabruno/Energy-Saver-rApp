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
from pathlib import Path
from typing import Dict, Any

# Add current directory to path for absolute imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import the heuristic model using absolute imports
from heuristic import run_heuristic
from classes import UE, E2_Node


def run_heuristic_optimization(input_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrapper function to make heuristic-model compatible with main application.
    
    Args:
        input_json (Dict): Input data in the format expected by main application
        
    Returns:
        Dict: Optimization results in the format expected by main application
    """
    try:
        print(f"Processing {len(input_json['users'])} users with heuristic optimization")
        
        # Configuration parameters (similar to the optimal model)
        E2Ns_BW = 100
        E2Ns_TX = 20
        E2Ns_RF = 12.9
        E2Ns_AMP = 0.388
        random_seed = 10
        random.seed(random_seed)
        
        # Users demands profile
        demands_profile = [32, 25, 6, 3, 15, 12, 3, 1.5]
        
        # Create the E2 Nodes dict based on the input data
        E2Ns = {"E2_nodes": []}
        tmp = []
        ID_to_nodebid_and_PCI = {}
        ID_to_IMSI = {}
        count = 0
        
        # Process input to create E2N mappings
        for user in input_json["users"]:
            if (user["nodebid"], user["pci"]) not in tmp:
                tmp.append((user["nodebid"], user["pci"]))
                ID_to_nodebid_and_PCI[count] = (user["nodebid"], user["pci"])
                E2Ns["E2_nodes"].append({
                    "ID": count,
                    "nodebid": user["nodebid"],
                    "PCI": user["pci"],
                    "bandwidth": E2Ns_BW,
                    "max_power": E2Ns_TX,
                    "RF_consumption": E2Ns_RF,
                    "Power_amp_efficiency": E2Ns_AMP
                })
                count += 1
        
        # Create users dict with channel gains
        UEs = {"users": []}
        user_count = 0
        
        # Process each user and calculate channel gains
        for user in input_json["users"]:
            imsi = user["IMSI"]
            
            # Check if we already processed this IMSI
            existing_user_id = None
            for existing_imsi, existing_id in ID_to_IMSI.items():
                if existing_imsi == imsi:
                    existing_user_id = existing_id
                    break
            
            if existing_user_id is None:
                # New user
                ID_to_IMSI[imsi] = user_count
                
                # Generate demand randomly from profile
                demand = random.choice(demands_profile)
                
                # Calculate channel gains for all E2 nodes
                channel_gain = {}
                for e2n_id, (nodebid, pci) in ID_to_nodebid_and_PCI.items():
                    if user["nodebid"] == nodebid and user["pci"] == pci:
                        # Convert SINR to channel gain (simplified conversion)
                        sinr_db = user["sinr"]
                        channel_gain[e2n_id] = 10 ** (sinr_db / 10)  # Convert dB to linear
                    else:
                        # Assign lower channel gain for other E2 nodes
                        channel_gain[e2n_id] = 10 ** ((user["sinr"] - 10) / 10)  # 10 dB penalty
                
                UEs["users"].append({
                    "ID": user_count,
                    "demand": demand,
                    "channel_gain": channel_gain
                })
                
                user_count += 1
        
        print(f"Created {len(E2Ns['E2_nodes'])} E2 nodes and {len(UEs['users'])} users for heuristic optimization")
        
        # Run the heuristic optimization
        total_BW = len(E2Ns["E2_nodes"]) * E2Ns_BW
        result = run_heuristic(E2Ns, UEs, total_BW)
        connections, E2N_info, solution = result[0], result[1], result[2]
        
        # Transform results to expected format
        json_solution = {
            "Users admission": [],
            "GNB_config": []
        }
        
        # Build users admission list
        for user_id in connections:
            e2n_id = connections[user_id]
            if e2n_id in ID_to_nodebid_and_PCI:
                # Find the original IMSI for this user
                original_imsi = None
                for imsi, uid in ID_to_IMSI.items():
                    if uid == user_id:
                        original_imsi = imsi
                        break
                
                if original_imsi:
                    json_solution["Users admission"].append({
                        "IMSI": original_imsi,
                        "gnb": ID_to_nodebid_and_PCI[e2n_id][0],
                        "pci": ID_to_nodebid_and_PCI[e2n_id][1]
                    })
        
        # Build GNB configuration
        GNB_config_dict = {}
        
        # Initialize all gNBs
        for e2n_id in ID_to_nodebid_and_PCI:
            gnb_id = ID_to_nodebid_and_PCI[e2n_id][0]
            if gnb_id not in GNB_config_dict:
                GNB_config_dict[gnb_id] = {
                    "gnb": gnb_id,
                    "status": "powered_off",
                    "all_pcis": []
                }
        
        # Add PCI configurations
        for e2n_id in ID_to_nodebid_and_PCI:
            gnb_id = ID_to_nodebid_and_PCI[e2n_id][0]
            pci = ID_to_nodebid_and_PCI[e2n_id][1]
            
            if e2n_id in E2N_info.keys():
                pci_config = {
                    "pci": pci,
                    "bandwidth (MHz)": E2N_info[e2n_id]["bandwidth"],
                    "radioPower (dBm)": E2N_info[e2n_id]["power"],
                    "status": "active"
                }
                # Mark gNB as active if it has active PCIs
                GNB_config_dict[gnb_id]["status"] = "active"
            else:
                pci_config = {
                    "pci": pci,
                    "bandwidth (MHz)": None,
                    "radioPower (dBm)": None,
                    "status": "powered_off"
                }
            
            GNB_config_dict[gnb_id]["all_pcis"].append(pci_config)
        
        # Update gNB status based on active PCIs
        for gnb_id in GNB_config_dict:
            active_pcis = [pci for pci in GNB_config_dict[gnb_id]["all_pcis"] if pci["status"] == "active"]
            total_pcis = len(GNB_config_dict[gnb_id]["all_pcis"])
            
            if len(active_pcis) == 0:
                GNB_config_dict[gnb_id]["status"] = "powered_off"
            elif len(active_pcis) == total_pcis:
                GNB_config_dict[gnb_id]["status"] = "active"
            else:
                GNB_config_dict[gnb_id]["status"] = "partial"
        
        # Convert to list format
        for gnb in GNB_config_dict:
            json_solution["GNB_config"].append(GNB_config_dict[gnb])
        
        print(f"Heuristic optimization completed: {len(json_solution['Users admission'])} users admitted, "
              f"{len(json_solution['GNB_config'])} GNBs configured")
        
        return {
            "Users admission": json_solution["Users admission"],
            "GNB_config": json_solution["GNB_config"]
        }
        
    except Exception as e:
        print(f"Heuristic optimization failed: {e}")
        import traceback
        traceback.print_exc()
        return {"Users admission": [], "GNB_config": []}


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
