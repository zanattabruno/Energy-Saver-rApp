import logging
import argparse
import yaml
import json
import random
from rapp_catalogue_client import rAppCatalalogueClient


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

    def run(self):
        self.logger.info('Running the energy saver application.')
        self.logger.debug('Configuration: %s', self.config)
        self.load_e2nodelist()
        self.e2nodelist = self.change_radio_power(self.e2nodelist)

    def load_e2nodelist(self):
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
            node['radioPower'] = round(random.uniform(0.0, 55.0), 2)  # Change radioPower to a random value between 0 and 55 with 2-digit precision
        self.logger.info('Updated E2NodeList: %s', json.dumps(e2nodelist))
        return e2nodelist
    
if __name__ == "__main__":
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
    energy_saver.run()
