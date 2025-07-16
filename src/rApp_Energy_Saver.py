import logging
import argparse
import yaml
import json
import os


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


def transform_metrics_for_optimization(metrics):
    """
    Transform Prometheus SINR metrics into the format expected by the optimization model.
    
    Args:
        metrics (dict): Organized SINR metrics from Prometheus in format:
                       {imsi: {gnbid: {pci: sinr_value}}}
    
    Returns:
        dict: Transformed metrics in format expected by run_optimization:
              {"users": [{"IMSI": imsi, "nodebid": gnbid, "sinr": sinr_value, ...}]}
    """
    logger = logging.getLogger(__name__)
    
    if not metrics:
        logger.warning("No metrics provided for transformation")
        return {"users": []}
    
    transformed_users = []
    
    for imsi, gnb_data in metrics.items():
        for gnbid, pci_data in gnb_data.items():
            for pci, sinr_value in pci_data.items():
                user_entry = {
                    "IMSI": imsi,
                    "nodebid": gnbid,
                    "sinr": sinr_value,
                    "rrc_state": 1,  # Default value
                    "rsrp": -60,     # Default value (could be enhanced with actual RSRP metrics)
                    "rsrq": 1        # Default value (could be enhanced with actual RSRQ metrics)
                }
                transformed_users.append(user_entry)
    
    logger.info(f"Transformed {len(transformed_users)} user entries for optimization")
    return {"users": transformed_users}


def run_energy_optimization(metrics, logger):
    """
    Run the energy optimization model using the collected metrics.
    
    Args:
        metrics (dict): SINR metrics from Prometheus
        logger (logging.Logger): Logger instance
    
    Returns:
        dict: Optimization solution with user admissions and GNB configurations
    """
    from optimal_model.run_model import run_optimization
    
    # Transform metrics to the format expected by the optimization model
    transformed_input = transform_metrics_for_optimization(metrics)
    
    if not transformed_input["users"]:
        logger.error("No users found in metrics for optimization")
        return {"Users admission": [], "GNB_config": []}
    
    logger.info(f"Running optimization with {len(transformed_input['users'])} user entries")
    
    try:
        optimization_result = run_optimization(transformed_input)
        logger.info("Optimization completed successfully")
        return optimization_result
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        return {"Users admission": [], "GNB_config": []}


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
    
    # Run energy optimization using the collected metrics
    optimization_result = run_energy_optimization(metrics, logger)
    print(f"Optimization result: {optimization_result}")
    
    # Save the optimization result to a file
    import os
    output_file = os.path.join(os.path.dirname(__file__), "optimal_model", "solution.json")
    with open(output_file, 'w') as f:
        json.dump(optimization_result, f, indent=4)
    logger.info(f"Optimization result saved to {output_file}")