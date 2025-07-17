from docplex.cp.model import CpoModel
import json
from optimal_model.classes import UE, E2_Node
import math
import sys


def define_model(UEs, E2Ns, total_BW, UE_PCI_combinations=None, pci_weight=1.0):
    """
    Define optimization model that minimizes both energy consumption and number of active PCIs.
    
    Args:
        UEs: List of user equipment objects
        E2Ns: List of E2 Node objects  
        total_BW: Total bandwidth available
        UE_PCI_combinations: List of (ue_id, e2_id, pci) tuples representing valid UE-gNB-PCI combinations
        pci_weight: Weight for PCI minimization in objective function
    """
    
    # If no PCI combinations provided, create default combinations
    if UE_PCI_combinations is None:
        admission_pos = [(ue.ID, e2.ID) for ue in UEs for e2 in E2Ns]
        # For backward compatibility, assume each gNB has a default PCI
        UE_PCI_combinations = [(ue.ID, e2.ID, f"pci_{e2.ID}") for ue in UEs for e2 in E2Ns]
    else:
        admission_pos = [(combo[0], combo[1]) for combo in UE_PCI_combinations]
    
    E2s_power = [e2.ID for e2 in E2Ns]
    
    # Extract unique PCIs from combinations
    unique_pcis = list(set([combo[2] for combo in UE_PCI_combinations]))
    
    print(f"DEBUG: Total UE-PCI combinations: {len(UE_PCI_combinations)}")
    print(f"DEBUG: Unique PCIs available: {unique_pcis}")
    print(f"DEBUG: Number of UEs: {len(UEs)}")
    print(f"DEBUG: Number of E2Ns: {len(E2Ns)}")
    print(f"DEBUG: PCI weight: {pci_weight}")
    
    mdl = CpoModel()
    
    # Decision variables
    mdl.x = mdl.binary_var_dict([(combo[0], combo[1], combo[2]) for combo in UE_PCI_combinations], name="x") # UE assigned to E2N with specific PCI
    mdl.y = mdl.integer_var_dict(E2s_power, name="y") # transmit power for each E2N
    mdl.z = mdl.binary_var_dict(E2s_power, name="z") # E2N activation
    mdl.pci_active = mdl.binary_var_dict(unique_pcis, name="pci_active") # PCI activation
    mdl.r = mdl.integer_var_dict([(combo[0], combo[1], combo[2]) for combo in UE_PCI_combinations], name="r") # bandwidth allocation
    
    # New variables for PCI-level resource allocation
    mdl.pci_power = mdl.integer_var_dict([(e2.ID, pci) for e2 in E2Ns for pci in unique_pcis], name="pci_power") # Power per PCI
    mdl.pci_bandwidth = mdl.integer_var_dict([(e2.ID, pci) for e2 in E2Ns for pci in unique_pcis], name="pci_bandwidth") # BW per PCI

    # Objective function: minimize energy consumption + weighted PCI activation
    # Power consumption is now calculated at PCI level
    pci_power_energy = mdl.sum(mdl.pci_power[(e2.ID, pci)]/e2.Power_amp_efficiency 
                              for e2 in E2Ns for pci in unique_pcis)
    RF_energy = mdl.sum(mdl.z[e2.ID] * e2.RF_consumption for e2 in E2Ns)
    pci_penalty = pci_weight * mdl.sum(mdl.pci_active[pci] for pci in unique_pcis)
    
    print(f"DEBUG: Energy terms will be balanced against PCI penalty of weight {pci_weight}")
    
    mdl.minimize(pci_power_energy + RF_energy + pci_penalty)

    # Constraints
    
    # Bandwidth and power constraints for each E2N-UE-PCI combination
    for combo in UE_PCI_combinations:
        ue_id, e2_id, pci = combo
        e2 = next(e2 for e2 in E2Ns if e2.ID == e2_id)
        mdl.add(mdl.r[combo] <= mdl.pci_bandwidth[(e2_id, pci)])  # Use PCI-specific bandwidth
        mdl.add(mdl.r[combo] >= mdl.x[combo] * 0.00000001)
    
    # Total bandwidth constraint (global)
    mdl.add(mdl.sum(mdl.r[combo] for combo in UE_PCI_combinations) <= total_BW)

    # PCI resource sharing constraints within each gNodeB
    for e2 in E2Ns:
        # Total power allocated to all PCIs cannot exceed gNodeB power budget
        mdl.add(mdl.sum(mdl.pci_power[(e2.ID, pci)] for pci in unique_pcis) <= mdl.y[e2.ID])
        
        # Total bandwidth allocated to all PCIs cannot exceed gNodeB bandwidth
        mdl.add(mdl.sum(mdl.pci_bandwidth[(e2.ID, pci)] for pci in unique_pcis) <= e2.BW)
        
        # PCI power must be zero if PCI is not active on this gNodeB
        for pci in unique_pcis:
            pci_usage_on_e2 = mdl.sum(mdl.x[combo] 
                                     for combo in UE_PCI_combinations 
                                     if combo[1] == e2.ID and combo[2] == pci)
            # If no users on this PCI at this gNodeB, no power allocation
            mdl.add(mdl.pci_power[(e2.ID, pci)] <= pci_usage_on_e2 * e2.max_power)
            mdl.add(mdl.pci_bandwidth[(e2.ID, pci)] <= pci_usage_on_e2 * e2.BW)
            
        # gNodeB power constraints
        mdl.add(0 <= mdl.y[e2.ID])
        mdl.add(mdl.y[e2.ID] <= e2.max_power)

    # Each UE must be assigned to exactly one E2N-PCI combination
    for ue in UEs:
        ue_assignments = mdl.sum(mdl.x[combo] 
                               for combo in UE_PCI_combinations 
                               if combo[0] == ue.ID)
        mdl.add(ue_assignments == 1)
        
        # Throughput constraint for each UE-E2N-PCI combination
        for combo in UE_PCI_combinations:
            if combo[0] == ue.ID:
                ue_id, e2_id, pci = combo
                signal_power = 30  # 1W = 30dbm
                IN_dbm = signal_power - ue.channel_gain[e2_id]
                IN_watt = 10 ** ((IN_dbm/10) - 3)
                # Use PCI-specific power instead of total gNodeB power
                mdl.add((1 + ((10 ** ((mdl.pci_power[(e2_id, pci)]/10) - 3))/IN_watt)) ** mdl.r[combo] >= 
                       mdl.x[combo] * 2**(ue.demand))

    # gNodeB activation constraints
    for e2 in E2Ns:
        mdl.add(e2.max_power * mdl.z[e2.ID] >= mdl.y[e2.ID])
        mdl.add(mdl.y[e2.ID] >= mdl.z[e2.ID] * 0.0000001)
        
        # gNodeB is active if any UE is assigned to it
        e2_usage = mdl.sum(mdl.x[combo] 
                          for combo in UE_PCI_combinations 
                          if combo[1] == e2.ID)
        mdl.add(mdl.z[e2.ID] <= e2_usage)
        mdl.add(mdl.z[e2.ID] >= e2_usage / len(UEs))
    
    # PCI activation constraints: PCI is active if any UE is assigned to it
    for pci in unique_pcis:
        pci_usage = mdl.sum(mdl.x[combo] 
                           for combo in UE_PCI_combinations 
                           if combo[2] == pci)
        mdl.add(mdl.pci_active[pci] <= pci_usage)
        mdl.add(mdl.pci_active[pci] >= pci_usage / len(UEs))
    
    # Dynamic resource allocation: PCIs with more users get proportionally more resources
    for e2 in E2Ns:
        # Get all PCIs that could be active on this gNodeB
        relevant_pcis = [pci for pci in unique_pcis 
                        if len([c for c in UE_PCI_combinations if c[1] == e2.ID and c[2] == pci]) > 0]
        
        for pci in relevant_pcis:
            users_on_pci = mdl.sum(mdl.x[combo] 
                                  for combo in UE_PCI_combinations 
                                  if combo[1] == e2.ID and combo[2] == pci)
            
            # Minimum resource allocation for active PCIs (10% of gNodeB capacity per user)
            mdl.add(mdl.pci_bandwidth[(e2.ID, pci)] >= users_on_pci * (e2.BW * 0.1))
            mdl.add(mdl.pci_power[(e2.ID, pci)] >= users_on_pci * (e2.max_power * 0.1))
            
            # Maximum resource allocation (don't exceed gNodeB capacity)
            mdl.add(mdl.pci_bandwidth[(e2.ID, pci)] <= e2.BW)
            mdl.add(mdl.pci_power[(e2.ID, pci)] <= e2.max_power)
            
            # Proportional allocation: more users = more resources
            # Each user on this PCI should get at least equal share if possible
            max_users_per_pci = len([c for c in UE_PCI_combinations if c[1] == e2.ID and c[2] == pci])
            if max_users_per_pci > 0:
                # Fair share constraint: bandwidth per user should be at least minimum
                min_bw_per_user = e2.BW / (len(relevant_pcis) * max_users_per_pci) if len(relevant_pcis) > 0 else e2.BW
                mdl.add(mdl.pci_bandwidth[(e2.ID, pci)] >= users_on_pci * min_bw_per_user)

    msol = mdl.solve(execfile="/opt/ibm/ILOG/CPLEX_Studio221/cpoptimizer/bin/x86-64_linux/cpoptimizer")

    E2_bandwidth = {}
    connections = {}  # Now stores (ue_id: (e2_id, pci))
    E2N_info = {}
    users_TP = []
    RF_energy = 0
    active_pcis = []

    # Check if we have a valid solution
    if msol is None:
        print("No solution found by the optimizer")
        return [connections, E2N_info, {"max_BW": total_BW, "used_BW": 0, "users_TP": [], "users_PW": [], "total_energy": 0, "RF_energy": 0, "PW_energy": 0, "active_pcis": 0, "pci_resources": {}}]

    # Calculate RF energy from active E2Ns
    for i in E2s_power:
        z_value = msol.get_value(mdl.z[i])
        if z_value is not None and z_value > 0.8:
            RF_energy += E2Ns[i].RF_consumption

    # Extract active PCIs and their resource allocations
    pci_resources = {}
    for pci in unique_pcis:
        pci_value = msol.get_value(mdl.pci_active[pci])
        if pci_value is not None and pci_value > 0.8:
            active_pcis.append(pci)
            pci_resources[pci] = {}
            
            # Get resource allocation for this PCI on each gNodeB
            for e2 in E2Ns:
                pci_bw = msol.get_value(mdl.pci_bandwidth[(e2.ID, pci)])
                pci_pwr = msol.get_value(mdl.pci_power[(e2.ID, pci)])
                
                if pci_bw and pci_bw > 0:
                    pci_resources[pci][f"gnb_{e2.ID}"] = {
                        "bandwidth_mhz": int(pci_bw),
                        "power_dbm": int(pci_pwr)
                    }

    # Extract user assignments with PCI information
    for combo in UE_PCI_combinations:
        ue_id, e2_id, pci = combo
        x_value = msol.get_value(mdl.x[combo])
        if x_value is not None and x_value > 0.8:
            connections[ue_id] = (e2_id, pci)  # Store both E2N and PCI
            r_value = msol.get_value(mdl.r[combo])
            y_value = msol.get_value(mdl.y[e2_id])
            
            if r_value is None or y_value is None:
                continue
                
            if e2_id not in E2_bandwidth.keys():
                E2_bandwidth[e2_id] = int(r_value)
                E2N_info[e2_id] = {"bandwidth": int(r_value), "power": int(y_value)}
            else:
                E2_bandwidth[e2_id] += int(r_value)
                E2N_info[e2_id]["bandwidth"] += int(r_value)
                
            signal_power = 30
            ue_obj = next(ue for ue in UEs if ue.ID == ue_id)
            # Get the actual PCI power used for this UE
            pci_power_used = msol.get_value(mdl.pci_power[(e2_id, pci)])
            tp_ue = r_value * math.log2(1 + ((10 ** ((pci_power_used/10) - 3))/(signal_power/10**((signal_power - ue_obj.channel_gain[e2_id])/10 - 3))))
            users_TP.append(tp_ue)
            print("UE {} \t in \t E2N {} \t PCI {} \t PCI power {} \t signal power {} \t interference&noise {:.3f} \t BW {} MHz \tdemand {} Mbps\t\t throughput {} Mbps".format(ue_id, 
                                                                                                        e2_id,
                                                                                                        pci,
                                                                                                        pci_power_used,
                                                                                                        y_value,
                                                                                                        10/ue_obj.channel_gain[e2_id],
                                                                                                        r_value, 
                                                                                                        ue_obj.demand,
                                                                                                        int(tp_ue)))

    used_BW = 0
    for e2 in E2Ns:
        if e2.ID in E2_bandwidth:
            used_BW += E2_bandwidth[e2.ID]
    
    print(f"Total bandwidth used: {used_BW} MHz out of {total_BW} MHz")
    print(f"Users admitted: {len(connections)} out of {len(UEs)}")
    print(f"Active PCIs: {len(active_pcis)} out of {len(unique_pcis)} available PCIs")
    print(f"Active PCI list: {active_pcis}")
    print(f"PCI Resource Allocation: {pci_resources}")
    
    total_energy = msol.get_objective_value() if msol else 0
    total_energy = float(total_energy)

    solution = {
        "max_BW": total_BW,
        "used_BW": used_BW,
        "users_TP": users_TP,
        "users_PW": [ue.channel_gain for ue in UEs],
        "total_energy": total_energy,
        "RF_energy": float(RF_energy),
        "PW_energy": float(total_energy) - float(RF_energy),
        "active_pcis": len(active_pcis),
        "active_pci_list": active_pcis,
        "pci_resources": pci_resources
        }

    if msol:
        print("Solution status: " + msol.get_solve_status())
    
    return [connections, E2N_info, solution]

def run_model(input_E2N, input_UE, total_BW, pci_weight=1.0):    
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
    
    # Create UE-PCI combinations from input data (if available)
    UE_PCI_combinations = None
    if "pci_combinations" in input_UE:
        UE_PCI_combinations = input_UE["pci_combinations"]
    
    total_BW = 0
    for e2 in E2Ns:
        total_BW += e2.BW
    return define_model(UEs=UEs, E2Ns=E2Ns, total_BW=total_BW, 
                       UE_PCI_combinations=UE_PCI_combinations, pci_weight=pci_weight)