import json
from classes import UE, E2_Node
import math
import sys
import time


def find_E2N_object(E2Ns, e2n_ID):
    for e2n in E2Ns:
        if e2n.ID == e2n_ID:
            return e2n


def find_user_object(UEs, user_ID):
    for user in UEs:
        if user.ID == user_ID:
            return user


def best_E2N_users(UEs, E2Ns):
    best_users_by_E2Ns = {}
    for e2n in E2Ns:
        best_users_by_E2Ns[e2n.ID] = []
    
    for user in UEs:
        # Find the E2N ID with the highest channel gain for this user
        best_e2n_id = max(user.channel_gain, key=user.channel_gain.get)
        best_users_by_E2Ns[best_e2n_id].append(user.ID)
    
    return best_users_by_E2Ns


def E2N_users_sorted_by_channel(UEs, E2Ns):
    users_channel_in_E2N = {}
    for e2n in E2Ns:
        users_channel_in_E2N[e2n.ID] = {}
    
    for user in UEs:
        for e2n in E2Ns:
            users_channel_in_E2N[e2n.ID][user.ID] = user.channel_gain[e2n.ID]
    
    for e2n in users_channel_in_E2N:
        users_channel_in_E2N[e2n] = dict(sorted(users_channel_in_E2N[e2n].items(), key=lambda item: item[1], reverse=True))
    
    return users_channel_in_E2N


def activate_new_E2N(best_users_by_E2Ns, deactivated_E2Ns):
    max_users = 0
    for e2 in best_users_by_E2Ns:
        if len(best_users_by_E2Ns[e2]) > max_users and e2 in deactivated_E2Ns:
            max_users = len(best_users_by_E2Ns[e2])
            max_users_e2 = e2
    return max_users_e2


def calculate_BW_requirement(user, e2n, UEs, E2Ns, E2Ns_TP):
    e2n_reference_power = 100 # Reference power of E2N in mW, that means 20 dBm
    SINR_linear = user.channel_gain[e2n.ID]  # Already in linear scale from wrapper
    user_noise_interference = e2n_reference_power/SINR_linear # the result is noise in mW
    if user_noise_interference == 0:
        BW_requirement = 100 * 10**6  # If the user has no noise interference, we assume a maximum bandwidth requirement
    else:
        BW_requirement = user.demand/(math.log2(1 + (10**((E2Ns_TP[e2n.ID]/10))/user_noise_interference)))
    
    return BW_requirement


def increase_e2n_power(E2Ns_TP, e2n):
    E2Ns_TP[e2n.ID] += 4
    
    return E2Ns_TP


def print_heuristic_solution(admitted_users, E2Ns_admitted_users, UEs, users_BW_allocation, E2Ns_TP):
    print("----------------------------------------- HEURISTIC RESULT -----------------------------------------")
    
    if len(admitted_users) == len(UEs):
        print("All users were admitted")
    else:
        print("{} users were admitted and {} users were not admitted!".format(len(admitted_users), len(UEs) - len(admitted_users)))
    
    print("---------------------------------------- HEURISTIC SOLUTION ----------------------------------------")
    
    # for e2n in E2Ns_admitted_users:
    #     for user in E2Ns_admitted_users[e2n]:
    #         print("UE {} admitted by E2N {} with {} of bandwidth, {} of demand and {} of throughput".format(user, 
    #                                                                                                         e2n, 
    #                                                                                                         users_BW_allocation[user], 
    #                                                                                                         UEs[user].demand,
    #                                                                                                         users_BW_allocation[user] * math.log2(1 + ((10 ** ((E2Ns_TP[e2n]/10) - 3))/(10/UEs[user].channel_gain[e2n])))))


def try_to_decrease_power(e2n, E2Ns_TP, E2Ns_admitted_users, UEs):
    new_PW = E2Ns_TP[e2n.ID] - 1
    if new_PW <= 0:
        return False, E2Ns_TP, {}, {}
    new_users_BW_allocation = {}
    new_users_TP = {}
    total_BW_usage = 0
    success = False
    for user in E2Ns_admitted_users[e2n.ID]:
        user = find_user_object(UEs, user)
        e2n_reference_power = 100  # Reference power of E2N in mW, that means 20 dBm
        SINR_linear = user.channel_gain[e2n.ID]  # Already in linear scale from wrapper
        user_noise_interference = e2n_reference_power/SINR_linear  
        if user_noise_interference <= 0:
            user_new_BW = 100 * 10**6
        else:
            user_new_BW = user.demand/(math.log2(1 + (10**((new_PW/10))/(user_noise_interference))))
        new_users_BW_allocation[user.ID] = user_new_BW
        if user_noise_interference == 0:
            user_new_TP = 100 * 10**6
        else:
            user_new_TP = user_new_BW * math.log2(1 + ((10 ** ((new_PW/10)))/(user_noise_interference)))
        new_users_TP[user.ID] = user_new_TP
        total_BW_usage += user_new_BW
    if total_BW_usage <= e2n.BW:
        E2Ns_TP[e2n.ID] = new_PW
        success = True
    
    return success, E2Ns_TP, new_users_TP, new_users_BW_allocation



def define_heuristic(UEs, E2Ns, total_BW):
    start_time = time.time()
    best_users_by_E2Ns = best_E2N_users(UEs, E2Ns)
    users_channel_in_E2N = E2N_users_sorted_by_channel(UEs, E2Ns)
    admitted_users = []
    deactivated_E2Ns_IDs = [e2n.ID for e2n in E2Ns]

    E2Ns_BW_usage = {}
    E2Ns_TP = {}
    E2Ns_admitted_users = {}
    TOTAL_BW_usage = 0
    
    for e2n in E2Ns:
        E2Ns_BW_usage[e2n.ID] = 0
        E2Ns_TP[e2n.ID] = 0
        E2Ns_admitted_users[e2n.ID] = []
    
    users_BW_allocation = {}
    users_throughput = {}

    for user in UEs:
        users_BW_allocation[user.ID] = 0
        users_throughput[user.ID] = 0

    while True:
        e2n = activate_new_E2N(best_users_by_E2Ns, deactivated_E2Ns_IDs)
        e2n = find_E2N_object(E2Ns, e2n)
        deactivated_E2Ns_IDs.remove(e2n.ID)
        E2Ns_TP[e2n.ID] = 30 # max transmission power

        for user in users_channel_in_E2N[e2n.ID]:
            user = find_user_object(UEs, user)
            if user.ID not in admitted_users:
                BW_requirement = calculate_BW_requirement(user, e2n, UEs, E2Ns, E2Ns_TP)
                if E2Ns_BW_usage[e2n.ID] + BW_requirement <= e2n.BW and TOTAL_BW_usage + BW_requirement <= total_BW:
                    E2Ns_BW_usage[e2n.ID] += BW_requirement
                    TOTAL_BW_usage += BW_requirement
                    admitted_users.append(user.ID)
                    E2Ns_admitted_users[e2n.ID].append(user.ID)
                    users_BW_allocation[user.ID] = BW_requirement
                    e2n_reference_power = 100  # Reference power of E2N in mW, that means 20 dBm
                    SINR_linear = user.channel_gain[e2n.ID]  # Already in linear scale from wrapper
                    user_noise_interference = e2n_reference_power/SINR_linear  # the result is noise in mW
                    if user_noise_interference == 0:
                        users_throughput[user.ID] = 100 * 10**6
                    else:
                        users_throughput[user.ID] = users_BW_allocation[user.ID] * math.log2(1 + ((10 ** ((E2Ns_TP[e2n.ID]/10)))/user_noise_interference))
        if len(admitted_users) == len(UEs):
            break

        if len(deactivated_E2Ns_IDs) == 0:
            break
    
    for e2n in E2Ns:
        if e2n.ID not in deactivated_E2Ns_IDs:
            while True:
                success, E2Ns_TP, new_users_TP, new_users_BW_allocation  = try_to_decrease_power(e2n, E2Ns_TP, E2Ns_admitted_users, UEs)
                if success:
                    for user in E2Ns_admitted_users[e2n.ID]:
                        E2Ns_BW_usage[e2n.ID] -= users_BW_allocation[user]
                        E2Ns_BW_usage[e2n.ID] += new_users_BW_allocation[user]
                        users_throughput[user] = new_users_TP[user]
                        users_BW_allocation[user] = new_users_BW_allocation[user]
                else:
                    break
    total_time = time.time() - start_time
    print_heuristic_solution(admitted_users, E2Ns_admitted_users, UEs, users_BW_allocation, E2Ns_TP)

    connections = {}
    E2N_info = {}
    users_TP = []
    RF_energy = 0

    for e2n in E2Ns_TP:
        e2n = find_E2N_object(E2Ns, e2n)
        if E2Ns_TP[e2n.ID] > 0:
            RF_energy += e2n.RF_consumption
    
    connections = {}

    for user in admitted_users:
        for e2n in E2Ns_admitted_users:
            if user in E2Ns_admitted_users[e2n]:
                connections[user] = e2n
    
    for e2n in E2Ns:
        if e2n.ID not in deactivated_E2Ns_IDs:
            E2N_info[e2n.ID] = {"bandwidth": E2Ns_BW_usage[e2n.ID], "power": E2Ns_TP[e2n.ID]}
    
    for user in admitted_users:
        users_TP.append(users_throughput[user])

    used_BW = 0
    for e2 in E2Ns:
        used_BW += E2Ns_BW_usage[e2.ID]
    
    total_energy = 0
    for e2n in E2Ns:
        if e2n.ID not in deactivated_E2Ns_IDs:
            total_energy += e2n.RF_consumption
            total_energy += E2Ns_TP[e2n.ID]/e2n.Power_amp_efficiency

    # total_energy = float(total_energy)

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

    # if msol:
    #     print("Solution status: " + msol.get_solve_status())
    
    return [connections, E2N_info, solution]


def run_heuristic(input_E2N, input_UE, total_BW):    
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
    return define_heuristic(UEs=UEs, E2Ns=E2Ns,total_BW=total_BW)