def extract_radio_power(data):
    # This function takes the input data and extracts "nodebid: radioPower" as a string in a list
    result = []

    # Check if "GNB_config" is in the dictionary and it contains at least one item
    if "GNB_config" in data and len(data["GNB_config"]) > 0:
        # Iterate through each item in the GNB_config list
        for config in data["GNB_config"]:
            # Check if both "nodebid" and "radioPower (dBm)" keys exist in the item
            if "nodebid" in config and "radioPower (dBm)" in config:
                # Format the string as "nodebid: radioPower" and add it to the result list
                formatted_string = f'{config["nodebid"]}: {config["radioPower (dBm)"]}'
                result.append(formatted_string)

    return result