import logging
import argparse
import yaml
import json
import os

from rApp_catalogue_client import rAppCatalalogueClient
from prometheus_metrics_collector import PrometheusClient
from policy_manager import PolicyManager


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
    Create multiple PCI options per gNB to enable PCI minimization.
    
    Args:
        metrics (dict): Organized SINR metrics from Prometheus in format:
                       {imsi: {gnbid: {pci: sinr_value}}}
    
    Returns:
        dict: Transformed metrics in format expected by run_optimization:
              {"users": [{"IMSI": imsi, "nodebid": gnbid, "pci": pci, "sinr": sinr_value, ...}]}
    """
    logger = logging.getLogger(__name__)
    
    if not metrics:
        logger.warning("No metrics provided for transformation")
        return {"users": []}
    
    # First, collect all unique gNBs and their PCIs
    gnb_pci_map = {}
    for imsi, gnb_data in metrics.items():
        for gnbid, pci_data in gnb_data.items():
            if gnbid not in gnb_pci_map:
                gnb_pci_map[gnbid] = set()
            for pci in pci_data.keys():
                gnb_pci_map[gnbid].add(pci)
    
    logger.info(f"Found gNBs and their PCIs: {gnb_pci_map}")
    
    # Add debug information about the data structure
    total_measurements = sum(len(pci_data) for gnb_data in metrics.values() for pci_data in gnb_data.values())
    logger.info(f"Total IMSI-gNB-PCI measurements: {total_measurements}")
    logger.info(f"Unique IMSIs: {len(metrics)}")
    logger.info(f"Unique gNBs: {len(gnb_pci_map)}")
    total_pcis = sum(len(pcis) for pcis in gnb_pci_map.values())
    logger.info(f"Total PCIs across all gNBs: {total_pcis}")
    
    transformed_users = []
    
    # For each IMSI, create entries for all possible gNB-PCI combinations
    # This gives the optimizer choices between different PCIs for the same gNB
    for imsi, gnb_data in metrics.items():
        for gnbid, pci_data in gnb_data.items():
            # For each gNB this user can connect to, add all available PCIs
            # If the user has a measurement for a specific PCI, use that SINR
            # Otherwise, use a slightly degraded SINR to represent interference/sub-optimal conditions
            available_pcis = gnb_pci_map.get(gnbid, set())
            
            for pci in available_pcis:
                if pci in pci_data:
                    # User has actual measurement for this PCI
                    sinr_value = pci_data[pci]
                else:
                    # User doesn't have measurement for this PCI, estimate with penalty
                    # Use the best SINR from this gNB but with some degradation
                    best_sinr = max(pci_data.values()) if pci_data else 50
                    # Add more significant penalty and some randomness to encourage diversity
                    import random
                    penalty_factor = 0.6 + random.uniform(0, 0.2)  # 40-60% degradation
                    sinr_value = best_sinr * penalty_factor
                
                user_entry = {
                    "IMSI": imsi,
                    "nodebid": gnbid,
                    "pci": pci,
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
    
    # Initialize Policy Manager
    policy_manager = PolicyManager(config)
    
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
    
    # Parse optimization result to A1 policy instance format
    policy_instance = policy_manager.parse_optimization_to_policy(optimization_result)
    print(f"Policy instance: {policy_instance}")
    
    # Log the optimization result and policy instance in debug mode
    logger.debug(f"Optimization result: {json.dumps(optimization_result, indent=2)}")
    logger.debug(f"Generated policy instance: {json.dumps(policy_instance, indent=2)}")
    
    # Deploy the policy instance to Near-RT RIC
    deployment_success = policy_manager.deploy_policy_instance(policy_instance)
    if deployment_success:
        print(f"Policy successfully deployed with ID: {policy_instance.get('policy_id')}")
    else:
        print("Policy deployment failed. Check logs for details.")