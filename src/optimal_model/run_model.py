import random
from optimal_model.model import run_model
import json


# python3 run_model.py 10 4 100 30 12.9 0.388



def run_optimization(input_json):
    n_UEs = 10
    n_E2Ns = 3
    E2Ns_BW = 100
    E2Ns_TX = 30
    E2Ns_RF = 12.9
    E2Ns_AMP = 0.388
    random_seed = 10
    random.seed(random_seed)
    demands_profile = [32, 25, 6, 3, 15, 12, 3, 1.5]

    #input_json = json.load(open("../input_scenarios/new_input_file.json"))


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
    
    sol = run_model(E2Ns, UEs, total_BW=200)

    connections = sol[0]
    E2N_info = sol[1]
    solution = sol[2]

    json_solutoin = {"Users admission": [],
                 "GNB_config": []}

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

    return json_solutoin