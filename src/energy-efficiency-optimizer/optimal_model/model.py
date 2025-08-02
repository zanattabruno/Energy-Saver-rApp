from docplex.cp.model import CpoModel
import json
from classes import UE, E2_Node
import math
import sys
import time


def define_model(UEs, E2Ns, total_BW):

    admission_pos = [(ue.ID, e2.ID) for ue in UEs for e2 in E2Ns]
    E2s_power = [e2.ID for e2 in E2Ns]
    
    mdl = CpoModel()
    mdl.set_parameters(TimeLimit=60*60)
    
    # variable that determines if a user is admitted to an E2N
    mdl.x = mdl.binary_var_dict(admission_pos, name="x")
    # variable that determines the E2N power in dBm
    mdl.y = mdl.integer_var_dict(E2s_power, name="y")
    # variable that determines if an E2N is powered on - by looking to the set of variavbles y (power > 0 means powered on)
    mdl.z = mdl.binary_var_dict(E2s_power, name="z")
    # variable that determines the amount of bandwidth allocated to each user in each E2N
    mdl.r = mdl.integer_var_dict(admission_pos, name="r")

    # calculates the variable power consumption of the E2 Nodes - it varies according to the power used by the E2 Node - Transmission power consumption
    power_energy = mdl.sum(mdl.y[e2.ID]/e2.Power_amp_efficiency for e2 in E2Ns)
    # calculates the fixed energy consumption of the E2 Nodes - it is counted for each E2 Node that is powered on - Activation power consumption
    RF_energy = mdl.sum(mdl.z[e2.ID] * e2.RF_consumption for e2 in E2Ns)
    
    # defines the objective function to minimize the total energy consumption 
    mdl.minimize(power_energy + RF_energy)

    # this constrainsts defines that if a user is admitted to an E2 Node, the amount of bandwidth allocated to that user in that E2 Node must be greater than zero, or zero if the user is not admitted
    # this is a linearization of the product of x and r
    for e2 in E2Ns:
        for ue in UEs:
            mdl.add(mdl.r[ue.ID, e2.ID] <= e2.BW)
            mdl.add(mdl.r[ue.ID, e2.ID] >= mdl.x[ue.ID, e2.ID] * 0.00000001)
    
    # this constraint defines that the total bandwidth used by all E2 Nodes must not exceed the total bandwidth available for the system - IT IS NOT THE TOTAL BANDWIDTH OF THE E2 NODES
    # mdl.add(mdl.sum(mdl.r[ue.ID, e2.ID] for e2 in E2Ns for ue in UEs) <= total_BW) # the distributed resource in MHz must respect the total bandwidth of ours BSs

    # defines that if a E2 Node is powered on, the transmission power must be greater than zero - otherwise, the transmission power must be zero and the E2 Node is powered off
    for e2 in E2Ns:
        mdl.add(0 <= mdl.y[e2.ID])
        mdl.add(mdl.sum(mdl.r[ue.ID, e2.ID] * mdl.x[ue.ID, e2.ID] for ue in UEs) <= e2.BW)

    for ue in UEs:
        # defines that all users must be admitted to exactly one E2 Node
        mdl.add(mdl.sum(mdl.x[ue.ID, e2.ID] for e2 in E2Ns) == 1)
        for e2 in E2Ns:
            e2n_reference_power = 100
            # calculate the noise and interference experienced by the user to calculate the throughput
            SINR_linear = 10 ** (ue.channel_gain[e2.ID]/10)  # Convert mW - the channel gain is in dB, so we convert it to linear scale
            # convert the noise and interference to Watts
            user_noise_interference = e2n_reference_power/SINR_linear # the result is noise in mW
            # calculate the throughput of the user
            if user_noise_interference <= 0:
                user_noise_interference = -9999999
            
            # this constraint ensures that all users has its throughput demand satisfied according to the Shannon's capacity formula, the power of E2 Nodes and the allocated bandwidth to the user
            mdl.add((1 + ((10 ** (mdl.y[e2.ID]/10))/user_noise_interference)) ** mdl.r[(ue.ID, e2.ID)] >= mdl.x[ue.ID, e2.ID] * 2**(ue.demand)) # 2^(B * log_2(1 + SINR)) = (1 + SINR)^B

    for e2 in E2Ns:
        # these constraints ensure that the E2 Node maximum power is respected and if the E2 Node is powered on, the transmission power must be greater than zero
        mdl.add(e2.max_power * mdl.z[e2.ID] >= mdl.y[e2.ID])
        mdl.add(mdl.y[e2.ID] >= mdl.z[e2.ID] * 0.0000001) 

        # these constraints defines that if any user is associated with an E2 Node, the E2 Node must be powered on - with transmission power greater than zero
        mdl.add(mdl.z[e2.ID] <= mdl.sum(mdl.x[ue.ID, e2.ID] for ue in UEs))
        mdl.add(mdl.z[e2.ID] >= mdl.sum(mdl.x[ue.ID, e2.ID] for ue in UEs)/len(UEs))

    # Solver start time
    start_time = time.time()
    # solve the model with CPLEX CP Optimizer
    msol = mdl.solve(execfile="/opt/ibm/ILOG/CPLEX_Studio221/cpoptimizer/bin/x86-64_linux/cpoptimizer")
    # Solver end time
    total_time = time.time() - start_time

    # Preparing the solution to be returned
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
            
            e2n_reference_power = 100
            SINR_linear = 10 ** (ue.channel_gain[i[1]]/10)
            user_noise_interference = e2n_reference_power/SINR_linear
            
            if user_noise_interference <= 0:
                user_noise_interference = -9999999
            tp_ue = msol[mdl.r[i]] * math.log2(1 + ((10 ** (msol[mdl.y[i[1]]]/10))/user_noise_interference))
            users_TP.append(tp_ue)

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
        "PW_energy": float(total_energy) - float(RF_energy),
        "Time": total_time
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