from docplex.cp.model import CpoModel
import json
from optimal_model.classes import UE, E2_Node
import math
import sys


def define_model(UEs, E2Ns, total_BW):

    admission_pos = [(ue.ID, e2.ID) for ue in UEs for e2 in E2Ns]
    E2s_power = [e2.ID for e2 in E2Ns]
    
    mdl = CpoModel()
    mdl.x = mdl.binary_var_dict(admission_pos, name="x")
    mdl.y = mdl.integer_var_dict(E2s_power, name="y")
    mdl.z = mdl.binary_var_dict(E2s_power, name="z")
    mdl.r = mdl.integer_var_dict(admission_pos, name="r")

    power_energy = mdl.sum(mdl.y[e2.ID]/e2.Power_amp_efficiency for e2 in E2Ns)
    RF_energy = mdl.sum(mdl.z[e2.ID] * e2.RF_consumption for e2 in E2Ns)
    
    mdl.minimize(power_energy + RF_energy)

    for e2 in E2Ns:
        for ue in UEs:
            mdl.add(mdl.r[ue.ID, e2.ID] <= e2.BW)
            mdl.add(mdl.r[ue.ID, e2.ID] >= mdl.x[ue.ID, e2.ID] * 0.00000001)
    
    mdl.add(mdl.sum(mdl.r[ue.ID, e2.ID] for e2 in E2Ns for ue in UEs) <= total_BW) # the distributed resource in MHz must respect the total bandwidth of ours BSs

    for e2 in E2Ns:
        mdl.add(0 <= mdl.y[e2.ID]) # , "transmit power must not be negative (?)")
        mdl.add(mdl.sum(mdl.r[ue.ID, e2.ID] * mdl.x[ue.ID, e2.ID] for ue in UEs) <= e2.BW)

    for ue in UEs:
        mdl.add(mdl.sum(mdl.x[ue.ID, e2.ID] for e2 in E2Ns) == 1) # , "all users must be admitted")
        for e2 in E2Ns:
            int_and_noise = 10/ue.channel_gain[e2.ID]
            print(ue.ID, e2.ID, int_and_noise)
            mdl.add((1 + ((10 ** ((mdl.y[e2.ID]/10) - 3))/int_and_noise)) ** mdl.r[(ue.ID, e2.ID)] >= mdl.x[ue.ID, e2.ID] * 2**(ue.demand))

    for e2 in E2Ns:
        mdl.add(e2.max_power * mdl.z[e2.ID] >= mdl.y[e2.ID]) # , "if e2 is not used (Z = 0), Y must be zero")

        mdl.add(mdl.y[e2.ID] >= mdl.z[e2.ID] * 0.0000001) # , "if e2 is used (Z = 1) Y is > 0")

        mdl.add(mdl.z[e2.ID] <= mdl.sum(mdl.x[ue.ID, e2.ID] for ue in UEs)) # , "Z is 1 if E2 is used or 0 if not")
        mdl.add(mdl.z[e2.ID] >= mdl.sum(mdl.x[ue.ID, e2.ID] for ue in UEs)/len(UEs))

    msol = mdl.solve(execfile="/opt/ibm/ILOG/CPLEX_Studio221/cpoptimizer/bin/x86-64_linux/cpoptimizer")

    E2_bandwidth = {}
    connections = {}
    E2N_info = {}
    users_TP = []
    RF_energy = 0

    for i in E2s_power:
        if msol[mdl.z[i]] > 0.8:
            RF_energy += E2Ns[i].RF_consumption

    for i in admission_pos:
        if msol[mdl.x[i]] > 0.8:
            connections[i[0]] = i[1]
            if i[1] not in E2_bandwidth.keys():
                E2_bandwidth[i[1]] = int(msol[mdl.r[i]])
                E2N_info[i[1]] = {"bandwidth": int(msol[mdl.r[i]]), "power": int(msol[mdl.y[i[1]]])}
            else:
                E2_bandwidth[i[1]] += int(msol[mdl.r[i]])
                E2N_info[i[1]]["bandwidth"] += int(msol[mdl.r[i]])
            tp_ue = msol[mdl.r[i]] * math.log2(1 + ((10 ** ((msol[mdl.y[i[1]]]/10) - 3))/(10/UEs[i[0]].channel_gain[i[1]])))
            users_TP.append(tp_ue)
            print("UE {} \t in \t E2N {}\t signal power {} \t interference&noise {:.3f} \t BW {} MHz \tdemand {} Mbps\t\t throughput {} Mbps".format(i[0], 
                                                                                                        i[1], 
                                                                                                        msol[mdl.y[i[1]]],
                                                                                                        10/UEs[i[0]].channel_gain[i[1]],
                                                                                                        msol[mdl.r[i]], 
                                                                                                        UEs[i[0]].demand,
                                                                                                        int(tp_ue)))

    used_BW = 0
    for e2 in E2Ns:
        if e2.ID in E2_bandwidth:
            used_BW += E2_bandwidth[e2.ID]
    
    total_energy = msol.get_objective_value()

    total_energy = float(total_energy)

    solution = {
        "max_BW": total_BW,
        "used_BW": used_BW,
        "users_TP": users_TP,
        "users_PW": [ue.channel_gain for ue in UEs],
        "total_energy": total_energy,
        "RF_energy": float(RF_energy),
        "PW_energy": float(total_energy) - float(RF_energy)
        }

    if msol:
        print("Solution status: " + msol.get_solve_status())
    
    return [connections, E2N_info, solution]

def run_model(input_E2N, input_UE, total_BW):    
    UEs = []
    for user in input_UE["users"]:
        UEs.append(UE(user["ID"], 
                      user["demand"], 
                      user["channel_gain"]))

    E2Ns = []    
    for E2N in input_E2N["E2_nodes"]:
        E2Ns.append(E2_Node(E2N["ID"], 
                            E2N["bandwidth"],
                            E2N["max_power"],
                            E2N["RF_consumption"],
                            E2N["Power_amp_efficiency"]))
    
    total_BW = 0
    for e2 in E2Ns:
        total_BW += e2.BW
    return define_model(UEs=UEs, E2Ns=E2Ns,total_BW=total_BW)