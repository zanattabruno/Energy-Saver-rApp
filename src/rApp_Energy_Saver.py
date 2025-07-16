import logging
import argparse
import yaml
import json


from rApp_catalogue_client import rAppCatalalogueClient
from prometheus_metrics_collector import PrometheusClient


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
    parser.add_argument('-c','--config', type=str, default=DEFAULT_CONFIG_FILE_PATH,
                        help='Path to the configuration file.')
    return parser.parse_args()


def collect_sinr_metrics(config, logger):
    """
    Collect SINR metrics from Prometheus and return as a dictionary.
    
    Args:
        config (dict): Configuration dictionary
        logger (logging.Logger): Logger instance
    Returns:
        tuple: (dict: Organized SINR metrics, int: Number of distinct IMSIs)
    """
    prometheus_url = config.get('nearrtric', {}).get('prometheus_url')
    if not prometheus_url:
        logger.error("Prometheus URL not configured in config.yaml")
        return {}, 0
    prom_client = PrometheusClient(prometheus_url)
    logger.info("Collecting all SINR metrics")
    metrics = prom_client.collect_sinr_metrics()
    
    # Count distinct IMSIs - the keys of the metrics dict are the IMSIs
    imsi_count = len(metrics) if metrics else 0
    logger.info(f"Found {imsi_count} distinct IMSIs")
    
    return (metrics if metrics else {}, imsi_count)


if __name__ == "__main__":

    args = parse_arguments()
    # Load the configuration from the file
    with open(args.config, 'r') as file:
        config = yaml.safe_load(file)
    logger = setup_logging(config)
    
    # Original rApp catalogue registration functionality
    register = rAppCatalalogueClient(args.config)
    
    if register.register_service():
        logger.info("Service successfully registered on rApp catalogue.")
    else:
        logger.error("Failed to register service.")

    metrics, imsi_count = collect_sinr_metrics(config, logger)
    print(f"Metrics: {metrics}")
    print(f"Distinct IMSIs count: {imsi_count}")