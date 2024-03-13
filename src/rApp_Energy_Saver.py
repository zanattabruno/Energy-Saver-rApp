import logging
import argparse
import yaml
import json
import random
import requests
import threading

from rApp_catalogue_client import rAppCatalalogueClient
from UE_Generator import integrate_estimates_with_original_data
from Solution_Tools import extract_radio_power, update_radio_power
from UE_Consumer import UEConsumer
from time import sleep
from optimal_model.run_model import run_optimization
import time

DEFAULT_CONFIG_FILE_PATH = "src/config/config.yaml"

def setup_logging(config):
    """
    Configures logging settings for the application.

    Args:
        config (dict): Configuration settings including the desired logging level.

    Returns:
        logging.Logger: Configured logger instance.
    """
    level = config.get('logging', {}).get('level', 'INFO').upper()  # Default to INFO if not specified
    numeric_level = getattr(logging, level, None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {level}')
    logging.basicConfig(level=numeric_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

def parse_arguments():
    """
    Parses command line arguments specific to the RIC Optimizer.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description='RIC Optimizer arguments.')
    parser.add_argument('--config', type=str, default=DEFAULT_CONFIG_FILE_PATH,
                        help='Path to the configuration file.')
    return parser.parse_args()


class EnergySaver:
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.e2nodelist = []
        self.policyradiopowerbody = {}
    
    def fill_policy_body(self, data):
        """
        Fills the policybody dictionary with the required values from the configuration and data.

        Args:
            config (dict): Configuration settings.
            data (list): List of E2 nodes.

        Returns:
            dict: Filled policybody dictionary.
        """

        policybody = {
            "ric_id": config['nonrtric']['ric_id'],
            "policy_id": str(random.randint(0000, 9999)),
            "service_id": config['nonrtric']['service_name'],
            "policy_data": {"E2NodeList": data},
            "policytype_id": config['nonrtric']['radiopower_policytype_id'],
        }
        self.policyradiopowerbody = policybody

        self.logger.debug('Policy body: %s', self.policyradiopowerbody)
        return self.policyradiopowerbody

    def load_e2nodelist(self):
        """
        Load the E2NodeList from the configuration and return it as a JSON string.

        Returns:
            str: JSON string representation of the E2NodeList.
            
        Raises:
            Exception: If there is an error while loading the E2NodeList.
        """
        try:
            self.e2nodelist = self.config.get('E2NodeList', [])
            self.logger.debug('E2NodeList: %s', self.e2nodelist)
            return json.dumps(self.e2nodelist)
        except Exception as e:
            self.logger.error('Failed to load E2NodeList: %s', e)
            return None

    def change_radio_power(self, e2nodelist):
        """
        Changes the value of radioPower in e2nodelist with random valid values for radio power.

        Args:
            e2nodelist (list): List of E2 nodes.

        Returns:
            list: Updated list of E2 nodes.
        """
        for node in e2nodelist:
            node['radioPower'] = round(random.uniform(0.0, 55.0), 1)  # Change radioPower to a random value between 0 and 55 with 2-digit precision
        self.logger.debug('Updated E2NodeList: %s', json.dumps(e2nodelist))
        return e2nodelist
    
    def put_policy(self, body):
        """
        Sends a PUT request to create a policy.

        Args:
            body (dict): The JSON body of the request.

        Returns:
            bool: True if the policy is created successfully, False otherwise.
        """
        complete_url = config['nonrtric']['base_url_pms'] + "/policies"
        print(complete_url)
        headers = {"content-type": "application/json"}
        self.logger.debug(f"Sending PUT request to {complete_url} with body: {body}")
        resp = requests.put(complete_url, json=body, headers=headers, verify=False)
        if not resp.ok:
            self.logger.info(f"Failed to create policy. Response: {resp}")
            return False
        else:
            self.logger.info("Policy created successfully.")
            return True

    def run(self):
        self.logger.info('Running the energy saver application.')
        self.logger.debug('Configuration: %s', self.config)
        self.load_e2nodelist()
        self.e2nodelist = self.change_radio_power(self.e2nodelist)
        self.fill_policy_body(self.e2nodelist)
        self.put_policy(self.policyradiopowerbody)
    
if __name__ == "__main__":
    ue_input_list = []
    ue_input_dict = {}
    last_run_number_of_ues = 0
    last_run_time = time.time()
    args = parse_arguments()
    # Load the configuration from the file
    with open(args.config, 'r') as file:
        config = yaml.safe_load(file)
    logger = setup_logging(config)
    register = rAppCatalalogueClient(args.config)
    
    if register.register_service():
        logger.info("Service successfully registered on rApp catalogue.")
    else:
        logger.error("Failed to register service.")
    energy_saver = EnergySaver(logger, config)
    ue_consumer = UEConsumer(logger, config)
    #energy_saver.run()

    thread = threading.Thread(target=ue_consumer.run)
    thread.start()

    # Main loop that runs as long as the trigger interval is enabled in the configuration.
    while config["trigger"]["interval"]["enable"]:
        # Synchronize access to UE (User Equipment) data using a condition variable.
        with ue_consumer.ue_data_condition:
            # Sleep for a specified interval before processing the UE data. This helps in controlling the rate of data processing.
            sleep(config["trigger"]["interval"]["seconds"])
            # Wait for the UE data condition to be signaled. This usually indicates that new UE data is available for processing.
            ue_consumer.ue_data_condition.wait()  
            # Log the current UE data for debugging purposes. The data is converted to a JSON string before logging.
            logger.debug(json.dumps(ue_consumer.ue_data))  
            # Convert the UE data from a dictionary to a list for further processing.
            ue_input_list = list(ue_consumer.ue_data.values())
            # Prepare the UE input data for optimization by integrating estimates with the original data and assigning it to a new dictionary.
            ue_input_dict['users'] = integrate_estimates_with_original_data(ue_input_list)
            # Run the optimization process with the prepared UE input data.
            solution = run_optimization(ue_input_dict)
            # Update the radio power configuration based on the optimization solution.
            update_radio_power(config, extract_radio_power(solution))
    
    # Main loop that runs as long as user variation trigger is enabled in the configuration.
    while config["trigger"]["user_variation"]["enable"]:
        # Synchronize access to UE (User Equipment) data using a condition variable.
        with ue_consumer.ue_data_condition:
            # Wait for the UE data condition to be signaled, indicating new UE data is available.
            ue_consumer.ue_data_condition.wait()  
            # Log the current state of UE data for debugging. The data is converted into a JSON string.
            logger.debug(json.dumps(ue_consumer.ue_data))
            # Extract UE data values, converting them from a dictionary to a list for further processing.
            ue_input_list = list(ue_consumer.ue_data.values())
            # Log the number of User Equipments (UEs) currently being processed.
            logger.info(f"Number of UEs: {len(ue_input_list)}")
            # Prepare the UE data for optimization by integrating additional estimates with the original data.
            ue_input_dict['users'] = integrate_estimates_with_original_data(ue_input_list)
            # Check if the minimum time since the last optimization run has been reached.
            if time.time() - last_run_time > config["trigger"]["user_variation"]["min_time_since_last_run_seconds"]:
                # Check if the user equipment variation threshold has been exceeded, allowing for a new optimization run.
                if last_run_number_of_ues * (1 + config["trigger"]["user_variation"]["percentage"]) < len(ue_input_list):
                    # Run the optimization process using the prepared UE data.
                    solution = run_optimization(ue_input_dict)
                    # Update the radio power configuration based on the results of the optimization.
                    update_radio_power(config, extract_radio_power(solution))
                    # Update the counters for the number of UEs and the last run time after a successful optimization.
                    last_run_number_of_ues = len(ue_input_list)
                    last_run_time = time.time()
                else:
                    # Log information indicating that the user equipment variation condition for optimization has not been met.
                    logger.info("Ue variation for running optimization is not met.")
            else:
                # Log information indicating that the minimum time requirement since the last optimization run has not been reached.
                logger.info("Minimum time since last run is not reached.")




