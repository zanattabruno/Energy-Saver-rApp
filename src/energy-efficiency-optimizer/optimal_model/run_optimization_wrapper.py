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
from typing import Dict, Any

# Add current directory to path for absolute imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import the energy-efficiency-optimizer model using absolute imports
from model import run_model
from classes import UE, E2_Node


def run_optimization(input_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrapper function to make energy-efficiency-optimizer compatible with main application.
    
    Args:
        input_json (Dict): Input data in the format expected by main application
        
    Returns:
        Dict: Optimization results in the format expected by main application
    """
    try:
        print(f"Processing {len(input_json['users'])} users with energy-efficiency-optimizer")
        
        # Configuration parameters (similar to the original script)
        E2Ns_BW = 100
        E2Ns_TX = 20
        E2Ns_RF = 12.9
        E2Ns_AMP = 0.388
        random_seed = 10
        random.seed(random_seed)
        
        # Users demands profile
        demands_profile = [32, 25, 6, 3, 15, 12, 3, 1.5]
        
        # Create the E2 Nodes dict based on the input file
        E2Ns = {"E2_nodes": []}
        tmp = []
        ID_to_nodebid_and_PCI = {}
        count = 0
        
        # Read the information from the input file and create the E2 Nodes dict
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
        
        # Users dict to be used in the optimization model
        UEs = {"users": []}
        tmp = []
        ID_to_IMSI = {}
        count = 0
        
        # Read the information from the input file and create the users dict
        for user in input_json["users"]:
            if user["IMSI"] not in tmp:
                ID_to_IMSI[count] = user["IMSI"]
                tmp.append(user["IMSI"])
                channel_gain = {}
                
                # Build channel gain mapping for this user
                for e2n_ID in ID_to_nodebid_and_PCI:
                    nodebid = ID_to_nodebid_and_PCI[e2n_ID][0]
                    pci = ID_to_nodebid_and_PCI[e2n_ID][1]
                    
                    # Find matching user entry for this nodebid/pci combination
                    found_sinr = None
                    for u in input_json["users"]:
                        if (u["nodebid"] == nodebid and 
                            u["pci"] == pci and 
                            u["IMSI"] == user["IMSI"]):
                            found_sinr = u["sinr"]
                            break
                    
                    if found_sinr is not None:
                        channel_gain[e2n_ID] = found_sinr
                    else:
                        # Use a default poor signal if no measurement available
                        channel_gain[e2n_ID] = -10  # Poor signal
                
                demand = random.choice(demands_profile)
                UE_ID = count
                count += 1
                UEs["users"].append({
                    "ID": UE_ID,
                    "channel_gain": channel_gain,
                    "demand": demand
                })
        
        # Run the optimization model
        sol = run_model(E2Ns, UEs, total_BW=100*25)
        
        connections = sol[0]
        E2N_info = sol[1]
        solution = sol[2]
        
        # Format the solution to match expected output format
        json_solution = {
            "Users admission": [],
            "GNB_config": [],
            "time": solution.get("Time", 0)
        }
        
        # Process user admissions
        for user in connections:
            if user in ID_to_IMSI and connections[user] in ID_to_nodebid_and_PCI:
                json_solution["Users admission"].append({
                    "IMSI": ID_to_IMSI[user],
                    "gnb": ID_to_nodebid_and_PCI[connections[user]][0],
                    "pci": ID_to_nodebid_and_PCI[connections[user]][1]
                })
        
        # Process GNB configurations
        tmp = []
        GNB_config_dict = {}
        
        # Initialize all GNBs
        for e2n in ID_to_nodebid_and_PCI:
            gnb_id = ID_to_nodebid_and_PCI[e2n][0]
            if gnb_id not in tmp:
                tmp.append(gnb_id)
                if e2n in E2N_info.keys():
                    GNB_config_dict[gnb_id] = {
                        "gnb": gnb_id,
                        "status": "active",
                        "all_pcis": []
                    }
                else:
                    GNB_config_dict[gnb_id] = {
                        "gnb": gnb_id,
                        "status": "powered_off",
                        "all_pcis": []
                    }
        
        # Add PCI configurations
        for e2n in ID_to_nodebid_and_PCI:
            gnb_id = ID_to_nodebid_and_PCI[e2n][0]
            pci = ID_to_nodebid_and_PCI[e2n][1]
            
            if e2n in E2N_info.keys():
                pci_config = {
                    "pci": pci,
                    "bandwidth (MHz)": E2N_info[e2n]["bandwidth"],
                    "radioPower (dBm)": E2N_info[e2n]["power"],
                    "status": "active"
                }
            else:
                pci_config = {
                    "pci": pci,
                    "bandwidth (MHz)": None,
                    "radioPower (dBm)": None,
                    "status": "powered_off"
                }
            
            GNB_config_dict[gnb_id]["all_pcis"].append(pci_config)
        
        # Convert to list format
        for gnb in GNB_config_dict:
            json_solution["GNB_config"].append(GNB_config_dict[gnb])
        
        print(f"Optimization completed: {len(json_solution['Users admission'])} users admitted, "
              f"{len(json_solution['GNB_config'])} GNBs configured")
        
        return {
            "Users admission": json_solution["Users admission"],
            "GNB_config": json_solution["GNB_config"]
        }
        
    except Exception as e:
        print(f"Energy-efficiency-optimizer failed: {e}")
        import traceback
        traceback.print_exc()
        return {"Users admission": [], "GNB_config": []}


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
