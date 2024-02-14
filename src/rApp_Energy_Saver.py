import logging
import argparse
import yaml
from rapp_catalogue_client import rAppCatalalogueClient


DEFAULT_CONFIG_FILE_PATH = "config/config.yaml"


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

    def run(self):
        self.logger.info('Running the energy saver application.')
        self.logger.info('Configuration: %s', self.config)


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
