import random
from optimal_model.model import run_model
import json


# python3 run_model.py 10 4 100 30 12.9 0.388



def run_optimization(input_json):
    n_UEs = 10
    n_E2Ns = 3
    E2Ns_BW = 500  # Increased bandwidth per E2N node
    E2Ns_TX = 50   # Increased max transmit power
    E2Ns_RF = 12.9
    E2Ns_AMP = 0.388
    random_seed = 10
    random.seed(random_seed)
    demands_profile = [1, 2, 3, 1.5, 2.5, 1.2, 0.8, 0.5]  # Lower demands to make problem more feasible

    #input_json = json.load(open("../input_scenarios/new_input_file.json"))

    print(f"Processing {len(input_json['users'])} users")

    # Dynamically adjust E2N resources based on number of users
    num_users = len(input_json['users'])
    
    # Scale E2N resources based on user count
    if num_users > 1000:
        E2Ns_BW = 1000  # Higher bandwidth for many users
        E2Ns_TX = 60    # Higher power
        total_bandwidth_multiplier = 2
    elif num_users > 500:
        E2Ns_BW = 800
        E2Ns_TX = 55
        total_bandwidth_multiplier = 1.5
    else:
        total_bandwidth_multiplier = 1


    E2Ns = {"E2_nodes": []}
    tmp = []
    ID_to_nodebid = {}
    ID_to_IMSI = {}
    IMSI_to_PCI = {}  # Map IMSI to their PCI for best connection
    count = 0

    # Create unique gNB entries
    for i in input_json["users"]:
        if i["nodebid"] not in tmp:
            tmp.append(i["nodebid"])
            ID_to_nodebid[count] = i["nodebid"]
            E2Ns["E2_nodes"].append({
                "ID": count,
                "nodebid": i["nodebid"],
                "bandwidth": E2Ns_BW,
                "max_power": E2Ns_TX,
                "RF_consumption": E2Ns_RF,
                "Power_amp_efficiency": E2Ns_AMP
            })
            count += 1

    # For each IMSI, find the best PCI (highest SINR) for each gNB
    UEs = {"users": []}
    tmp = []
    count = 0
    for i in input_json["users"]:
        if i["IMSI"] not in tmp:
            ID_to_IMSI[count] = i["IMSI"]
            
            # Find the best PCI for this IMSI among all available options
            best_pci = None
            best_sinr = -999
            for candidate in input_json["users"]:
                if candidate["IMSI"] == i["IMSI"] and candidate["sinr"] > best_sinr:
                    best_sinr = candidate["sinr"]
                    best_pci = candidate.get("pci", "unknown")
            
            IMSI_to_PCI[i["IMSI"]] = best_pci
            tmp.append(i["IMSI"])
            
            channel_gain = []
            for j in ID_to_nodebid:
                nodebid = ID_to_nodebid[j]
                print(nodebid)
                for u in input_json["users"]:
                    if u["nodebid"] == nodebid and u["IMSI"] == i["IMSI"]:
                        channel_gain.append(u["sinr"])
            demand = random.choice(demands_profile)
            UE_ID = count
            count += 1
            UEs["users"].append({
                "ID": UE_ID,
                "channel_gain": channel_gain,
                "demand": demand
                })
    
    # Create PCI combinations from input data
    pci_combinations = []
    for i in input_json["users"]:
        if i["IMSI"] in [ID_to_IMSI[ue_id] for ue_id in ID_to_IMSI]:
            ue_id = next(ue_id for ue_id in ID_to_IMSI if ID_to_IMSI[ue_id] == i["IMSI"])
            e2_id = next(e2_id for e2_id in ID_to_nodebid if ID_to_nodebid[e2_id] == i["nodebid"])
            pci = i.get("pci", f"pci_{e2_id}")
            pci_combinations.append((ue_id, e2_id, pci))
    
    print(f"DEBUG: Created {len(pci_combinations)} PCI combinations")
    print(f"DEBUG: Sample PCI combinations: {pci_combinations[:10]}")
    
    # Add PCI combinations to UEs data
    UEs["pci_combinations"] = pci_combinations
    
    sol = run_model(E2Ns, UEs, total_BW=int(1000 * total_bandwidth_multiplier), pci_weight=10.0)  # Reduce PCI weight to allow for better balance
    
    print(f"Processing completed. Found {len(sol[0])} user connections")

    connections = sol[0]
    E2N_info = sol[1]
    solution = sol[2]
    
    print(f"DEBUG: Solution keys: {solution.keys() if isinstance(solution, dict) else 'Not a dict'}")
    print(f"DEBUG: Connections type: {type(connections)}, E2N_info type: {type(E2N_info)}")

    json_solutoin = {"Users admission": [],
                 "GNB_config": [],
                 "Inactive_GNBs": [],
                 "Inactive_PCIs": []}
    
    print(f"Creating solution with {len(connections)} connections and {len(E2N_info)} E2N configurations")

    try:
        for user in connections:
            e2_id, pci = connections[user]  # connections now stores (e2_id, pci) tuples
            json_solutoin["Users admission"].append(
                {
                    "IMSI": ID_to_IMSI[user],
                    "gnb": ID_to_nodebid[e2_id],  # Changed from nodebid to gnb for clarity
                    "pci": pci  # Include actual PCI from optimization result
                })

        # Build complete GNB_config showing ALL gNBs (active and inactive)
        all_gnb_ids = set(ID_to_nodebid.keys())
        active_gnb_ids = set(E2N_info.keys())
        
        # Get all possible PCIs from input combinations
        all_pcis = set()
        for combo in UEs.get("pci_combinations", []):
            all_pcis.add(combo[2])  # combo[2] is the PCI
        
        # Get active PCI resources
        active_pci_resources = {}
        if "pci_resources" in solution:
            active_pci_resources = solution["pci_resources"]
        
        print(f"DEBUG: All gNBs: {[ID_to_nodebid[gid] for gid in all_gnb_ids]}")
        print(f"DEBUG: Active gNBs: {[ID_to_nodebid[gid] for gid in active_gnb_ids]}")
        print(f"DEBUG: All PCIs: {list(all_pcis)}")
        print(f"DEBUG: Active PCIs: {list(active_pci_resources.keys())}")
        
        # Process ALL gNBs (both active and inactive)
        for gnb_id in all_gnb_ids:
            if gnb_id in active_gnb_ids:
                # Active gNB
                gnb_config = {
                    "gnb": ID_to_nodebid[gnb_id],
                    "radioPower (dBm)": E2N_info[gnb_id]["power"],
                    "BW (MHz)": E2N_info[gnb_id]["bandwidth"],
                    "status": "active",
                    "all_pcis": []
                }
            else:
                # Inactive gNB
                gnb_config = {
                    "gnb": ID_to_nodebid[gnb_id],
                    "radioPower (dBm)": None,
                    "BW (MHz)": None,
                    "status": "powered_off",
                    "all_pcis": []
                }
            
            # Add ALL PCIs that could potentially be used on this gNB
            for pci in all_pcis:
                # Check if this PCI is actually active on this gNB
                gnb_key = f"gnb_{gnb_id}"
                pci_is_active = (pci in active_pci_resources and 
                               gnb_key in active_pci_resources.get(pci, {}))
                
                if pci_is_active:
                    # Active PCI
                    pci_config = {
                        "pci": pci,
                        "radioPower (dBm)": active_pci_resources[pci][gnb_key]["power_dbm"],
                        "BW (MHz)": active_pci_resources[pci][gnb_key]["bandwidth_mhz"],
                        "status": "active"
                    }
                else:
                    # Inactive PCI
                    pci_config = {
                        "pci": pci,
                        "radioPower (dBm)": None,
                        "BW (MHz)": None,
                        "status": "powered_off"
                    }
                
                gnb_config["all_pcis"].append(pci_config)
            
            json_solutoin["GNB_config"].append(gnb_config)
        
        # Also add separate PCI_config section for detailed PCI view
        if "pci_resources" in solution:
            pci_resources = solution["pci_resources"]
            if not json_solutoin.get("PCI_config"):
                json_solutoin["PCI_config"] = []
                
            for pci, gnb_allocations in pci_resources.items():
                for gnb_key, resources in gnb_allocations.items():
                    # Extract gNB ID from gnb_key (format: "gnb_X")
                    gnb_id = gnb_key.split('_')[1] if '_' in gnb_key else gnb_key
                    json_solutoin["PCI_config"].append(
                        {
                            "pci": pci,
                            "gnb": ID_to_nodebid.get(int(gnb_id), gnb_id) if gnb_id.isdigit() else gnb_id,
                            "radioPower (dBm)": resources["power_dbm"],
                            "BW (MHz)": resources["bandwidth_mhz"]
                        }
                    )
                    
    except Exception as e:
        print(f"ERROR in solution processing: {e}")
        print(f"DEBUG: connections = {connections}")
        print(f"DEBUG: solution = {solution}")
        import traceback
        traceback.print_exc()
        return {"Users admission": [], "GNB_config": []}

    return {"Users admission": json_solutoin["Users admission"], "GNB_config": json_solutoin["GNB_config"]}