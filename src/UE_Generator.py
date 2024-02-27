from collections import defaultdict


def integrate_estimates_with_original_data(ue_data):
    # Organize data by NodeB
    nodeb_metrics = defaultdict(lambda: defaultdict(list))
    for ue in ue_data:
        nodeb_metrics[ue['nodebid']]['rsrp'].append(ue['rsrp'])
        nodeb_metrics[ue['nodebid']]['sinr'].append(ue['sinr'])
        nodeb_metrics[ue['nodebid']]['rsrq'].append(ue['rsrq'])

    # Calculate average metrics for each NodeB
    avg_nodeb_metrics = {}
    for nodeb, metrics in nodeb_metrics.items():
        avg_nodeb_metrics[nodeb] = {
            'avg_rsrp': sum(metrics['rsrp']) / len(metrics['rsrp']),
            'avg_sinr': sum(metrics['sinr']) / len(metrics['sinr']),
            'avg_rsrq': sum(metrics['rsrq']) / len(metrics['rsrq']),
        }

    # Integrate estimated metrics for non-connected NodeBs into the original data
    enhanced_data = ue_data.copy()  # Use a copy to avoid modifying the original data in-place
    for ue in ue_data:
        for nodeb, avg_metrics in avg_nodeb_metrics.items():
            if nodeb != ue['nodebid']:  # Skip the NodeB the UE is currently connected to
                # Create a new entry with estimated metrics and rrc_state set to 0
                new_ue_entry = {
                    'IMSI': ue['IMSI'],
                    'nodebid': nodeb,
                    'rrc_state': 0,  # Indicating not currently connected
                    'rsrp': avg_metrics['avg_rsrp'],
                    'sinr': avg_metrics['avg_sinr'],
                    'rsrq': avg_metrics['avg_rsrq']
                }
                enhanced_data.append(new_ue_entry)  # Add the new entry to the original list

    return enhanced_data
