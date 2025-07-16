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
    count = 0

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

    UEs = {"users": []}
    tmp = []
    count = 0
    for i in input_json["users"]:
        if i["IMSI"] not in tmp:
            ID_to_IMSI[count] = i["IMSI"]
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
    
    sol = run_model(E2Ns, UEs, total_BW=int(1000 * total_bandwidth_multiplier))  # Scale total bandwidth
    
    print(f"Processing completed. Found {len(sol[0])} user connections")

    connections = sol[0]
    E2N_info = sol[1]
    solution = sol[2]

    json_solutoin = {"Users admission": [],
                 "GNB_config": []}
    
    print(f"Creating solution with {len(connections)} connections and {len(E2N_info)} E2N configurations")

    for user in connections:
        json_solutoin["Users admission"].append(
            {
                "IMSI": ID_to_IMSI[user],
                "nodebid": ID_to_nodebid[connections[user]]
            })

    for gnb in E2N_info:
        json_solutoin["GNB_config"].append(
            {
                "nodebid": ID_to_nodebid[gnb],
                "radioPower (dBm)": E2N_info[gnb]["power"],
                "BW (MHz)": E2N_info[gnb]["bandwidth"]
            }
        )
    
    print(f"Final solution: {len(json_solutoin['Users admission'])} users admitted, {len(json_solutoin['GNB_config'])} GNB configurations")

    return json_solutoin