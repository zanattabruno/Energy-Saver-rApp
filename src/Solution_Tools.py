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

    # Corrected iteration over config["O1"]["E2Nodes"]
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

    return results