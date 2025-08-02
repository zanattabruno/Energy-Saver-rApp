import random
import math
from model import run_model
import sys
import json


# python3 run_model.py 10 4 100 30 12.9 0.388
# define the number of users in the input file
n_UEs = int(sys.argv[1])
# define the maximum bandwidth for each E2 Node
E2Ns_BW = 100
# define the maximum transmission power of each E2 Node
E2Ns_TX = 20
# define the RF energy consumption of all E2 Nodes - it may be changed in the future to consider different RF consumption for each E2 Node
E2Ns_RF = 12.9
# define the power amplifier energy efficiency of all E2 Nodes - it may be changed in the future to consider different efficiency for each E2 Node
E2Ns_AMP = 0.388
# random seed to reproduce the same results
random_seed = 10
# set the random seed - the random function is used to generate the user demands based on a predefined profile options
random.seed(random_seed)

# users demands profile - it is used to generate the user demands randomly
demands_profile = [32, 25, 6, 3, 15, 12, 3, 1.5]

# read the input file with UEs, E2 Nodes and cells information
input_json = json.load(open("../input_scenarios/{}_users.json".format(n_UEs)))

# create the E2 Nodes dict based on the input file - this will be used in the optimization model
E2Ns = {"E2_nodes": []}
# help the mapping between E2 Node ID and (nodebid, PCI) tuple
tmp = []
# store the mapping between E2 Node ID and (nodebid, PCI) tuple
ID_to_nodebid_and_PCI = {}
# controll the ID of the E2 Nodes
count = 0

# read the information from the input file and create the E2 Nodes dict
for user in input_json["users"]:
    if (user["nodebid"], user["pci"]) not in tmp:
        tmp.append((user["nodebid"], user["pci"]))
        ID_to_nodebid_and_PCI[count] = (user["nodebid"], user["pci"])
        E2Ns["E2_nodes"].append({
            "ID": count,                    # integer value representing the E2 Node ID
            "nodebid": user["nodebid"],         # string value representing the E2 Node nodebid
            "PCI": user["pci"],                 # string value representing the E2 Node PCI
            "bandwidth": E2Ns_BW,               # integer value representing the E2 Node maximum bandwidth in MHz
            "max_power": E2Ns_TX,               # integer value representing the E2 Node maximum transmission power in dBm
            "RF_consumption": E2Ns_RF,          # float value representing the E2 Node RF energy consumption in W
            "Power_amp_efficiency": E2Ns_AMP    # float value representing the E2 Node power amplifier energy efficiency
        })
        count += 1
    
# users dict to be used in the optimization model
UEs = {"users": []}
# help the mapping between user ID and IMSI
tmp = []
# store the mapping between user ID and IMSI
ID_to_IMSI = {}
# controll the ID of the users
count = 0

# read the information from the input file and create the users dict
for user in input_json["users"]:
    if user["IMSI"] not in tmp:
        ID_to_IMSI[count] = user["IMSI"]
        tmp.append(user["IMSI"])
        channel_gain = {}
        for e2n_ID in ID_to_nodebid_and_PCI:
            nodebid = ID_to_nodebid_and_PCI[e2n_ID][0]
            pci = ID_to_nodebid_and_PCI[e2n_ID][1]
            for u in input_json["users"]:
                if u["nodebid"] == nodebid and u["pci"] == pci and u["IMSI"] == user["IMSI"]:
                    channel_gain[e2n_ID] = u["sinr"]
        demand = random.choice(demands_profile)
        UE_ID = count
        count += 1
        UEs["users"].append({
            "ID": UE_ID,                     # integer value representing the user ID
            "channel_gain": channel_gain,    # dict with E2 Node ID as key and channel gain in dB as value - this will be linearized in the optimization model
            "demand": demand                 # float value representing the user demand in Mbps
            })

sol = run_model(E2Ns, UEs, total_BW=100*25)

connections = sol[0]
E2N_info = sol[1]
solution = sol[2]

json_solutoin = {"Users admission": [],
                 "GNB_config": [],
                 "time": solution["Time"]}

for user in connections:
    json_solutoin["Users admission"].append(
        {
            "IMSI": ID_to_IMSI[user],
            "gnb": ID_to_nodebid_and_PCI[connections[user]][0],
            "pci": ID_to_nodebid_and_PCI[connections[user]][1]
        })

tmp = []
GNB_config_dict = {}

for e2n in ID_to_nodebid_and_PCI:
    if e2n in E2N_info.keys():
        if ID_to_nodebid_and_PCI[e2n][0] not in tmp:
            tmp.append(ID_to_nodebid_and_PCI[e2n][0])
            GNB_config_dict[ID_to_nodebid_and_PCI[e2n][0]] = {
                "gnb": ID_to_nodebid_and_PCI[e2n][0],
                "status": "active",
                "all_pcis": []
            }

for e2n in ID_to_nodebid_and_PCI:
    if ID_to_nodebid_and_PCI[e2n][0] not in GNB_config_dict:
        GNB_config_dict[ID_to_nodebid_and_PCI[e2n][0]] = {
            "gnb": ID_to_nodebid_and_PCI[e2n][0],
            "status": "powered_off",
            "all_pcis": []
        }
        
for e2n in ID_to_nodebid_and_PCI:
    if e2n in E2N_info.keys():
        GNB_config_dict[ID_to_nodebid_and_PCI[e2n][0]]["all_pcis"].append(
            {
                "pci": ID_to_nodebid_and_PCI[e2n][1],
                "bandwidth (MHz)": E2N_info[e2n]["bandwidth"],
                "radioPower (dBm)": E2N_info[e2n]["power"],
                "status": "active"
            }
        )
    else:
        GNB_config_dict[ID_to_nodebid_and_PCI[e2n][0]]["all_pcis"].append(
            {
                "pci": ID_to_nodebid_and_PCI[e2n][1],
                "bandwidth (MHz)": None,
                "radioPower (dBm)": None,
                "status": "powered_off"
            }
        )

for gnb in GNB_config_dict:
    json_solutoin["GNB_config"].append(GNB_config_dict[gnb])

json.dump(json_solutoin, open("solutions/{}_users.json".format(n_UEs), 'w'), indent=4)