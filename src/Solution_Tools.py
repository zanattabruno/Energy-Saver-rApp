import json
import random
import requests
import logging


logger = logging.getLogger(__name__)


def extract_radio_power(data):
    """
    Extracts "nodebid: radioPower" as a string in a list from the input data.

    Args:
        data (dict): The input data containing the GNB_config list.

    Returns:
        list: A list of strings in the format "nodebid: radioPower".

    """
    result = []

    if "GNB_config" in data and len(data["GNB_config"]) > 0:
        for config in data["GNB_config"]:
            if "nodebid" in config and "radioPower (dBm)" in config:
                formatted_string = f'{config["nodebid"]}: {config["radioPower (dBm)"]}'
                result.append(formatted_string)

    return result


def update_radio_power(config, radiopower):
    """
    Update the gain of E2 nodes using the O1 interface, with logging.

    Parameters:
    - config (dict): Configuration dictionary containing E2NodeList and O1 details.
    - radiopower (list of str): List of strings with node IDs and their respective gain settings.

    Returns:
    - dict: A dictionary with node IDs as keys and a tuple (bool, str) as values indicating success/failure and a message.
    """
    results = {}
    gain_dict = {}

    for entry in radiopower:
        node_id, gain = entry.split(': ')
        gain_dict[node_id] = float(gain)

    for o1_node in config["O1"]["E2Nodes"]:
        for node_id, url in o1_node.items():
            if node_id in gain_dict:
                payload = {"gain": gain_dict[node_id]}
                headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
                try:
                    response = requests.post(url, json=payload, headers=headers)
                    if response.status_code == 204:
                        results[node_id] = (True, "Successfully updated gain.")
                        logger.info(f"Successfully updated gain for {node_id}. Gain: {gain_dict[node_id]}")
                    else:
                        results[node_id] = (False, f"Failed to update gain. Status code: {response.status_code}, Response: {response.text}")
                        logger.warning(f"Failed to update gain for {node_id}. Status code: {response.status_code}, Response: {response.text}")
                except requests.exceptions.RequestException as e:
                    results[node_id] = (False, f"Request exception: {str(e)}")
                    logger.error(f"Request exception for {node_id}: {str(e)}")
            else:
                payload = {"gain": config['O1']['radioPower_off_gain']}
                headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
                try:
                    response = requests.post(url, json=payload, headers=headers)
                    if response.status_code == 204:
                        results[node_id] = (True, "Successfully updated gain.")
                        logger.info(f"Successfully updated gain for {node_id}. Gain: {config['O1']['radioPower_off_gain']}")
                    else:
                        results[node_id] = (False, f"Failed to update gain. Status code: {response.status_code}, Response: {response.text}")
                        logger.warning(f"Failed to update gain for {node_id}. Status code: {response.status_code}, Response: {response.text}")
                except requests.exceptions.RequestException as e:
                    results[node_id] = (False, f"Request exception: {str(e)}")
                    logger.error(f"Request exception for {node_id}: {str(e)}")

    return results

def update_handover_policy(config, solution):
    # Convert the input dictionary to the desired JSON format
    # This example assumes some values need to be hardcoded or generated. Adjust as needed.
    converted_json = {
        "ric_id": config['nonrtric']['ric_id'],
        "policy_id": str(random.randint(1, 999)),
        "service_id": config['nonrtric']['service_name'],
        "policy_data": {
            "E2NodeList": [
                {
                    # Assuming 'nodebid' from 'GNB_config' needs to be converted to 'nodebid' in 'E2NodeList'
                    "mcc": solution['GNB_config'][0]['nodebid'][:3],
                    "mnc": solution['GNB_config'][0]['nodebid'][3:6],
                    "nodebid": solution['GNB_config'][0]['nodebid'][7:],
                    "UEList": [{"imsi": user['IMSI']} for user in solution['Users admission']]
                }
                # If there were multiple nodes in 'GNB_config', you'd loop through them here
            ]
        },
        "policytype_id": config['nonrtric']['policytype_id']
    }
    
    # URL to post the data
    url = f"{config['nonrtric']['base_url_pms']}/policies"
    logger.debug(f'Policy instance:{json.dumps(converted_json, indent=4)}')
    # Headers to indicate JSON content
    headers = {"Content-Type": "application/json"}
    try:
        # Make the PUT request
        response = requests.put(url, json=converted_json, headers=headers)
        
        # Check if the POST request was successful
        if response.status_code == 200:
            logger.info("Policy instance update successfully.")
        elif response.status_code == 201:
            logger.info("Policy instance created successfully.")
        else:
            logger.error(f"Failed to post data. Status code: {response.status_code}, Response: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.exception(f"Request exception: {str(e)}")