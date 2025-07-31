"""
Energy Saver rApp Main Application.

This module implements the main application logic for the Energy Saver rApp,
including metrics collection, optimization, policy deployment, and scheduled execution.
"""

import logging
import argparse
import json
import sys
import signal
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from time import sleep

# Local imports
from utils.config_manager import ConfigManager
from utils.logging_manager import LoggingManager, log_function_calls
from utils.scheduler import FixedIntervalScheduler
from utils.exceptions import (
    ConfigurationError,
    MetricsCollectionError,
    OptimizationError,
    RAppRegistrationError
)
from rApp_catalogue_client import RAppCatalogueClient, rAppCatalalogueClient
from prometheus_metrics_collector import PrometheusClient
from policy_manager import PolicyManager

# Constants
DEFAULT_CONFIG_FILE_PATH = "src/config/config.yaml"
APPLICATION_NAME = "Energy Saver rApp"
APPLICATION_VERSION = "1.0.0"


class EnergySaverApplication:
    """
    Main application class for the Energy Saver rApp.
    
    This class orchestrates the entire energy saving workflow including:
    - Configuration management
    - Metrics collection from Prometheus
    - Energy optimization
    - Policy deployment
    - Scheduled execution at fixed intervals
    """
    
    def __init__(self, config_path: str):
        """
        Initialize the Energy Saver application.
        
        Args:
            config_path (str): Path to the configuration file
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        self.config_manager = ConfigManager(config_path)
        self.logger = self._setup_logging()
        
        # Initialize components
        self.prometheus_client: Optional[PrometheusClient] = None
        self.policy_manager: Optional[PolicyManager] = None
        self.rapp_client: Optional[rAppCatalalogueClient] = None
        self.scheduler: Optional[FixedIntervalScheduler] = None
        
        self.logger.info(f"Initializing {APPLICATION_NAME} v{APPLICATION_VERSION}")
        self._initialize_components()
        self._setup_signal_handlers()
    
    def _setup_logging(self) -> logging.Logger:
        """
        Set up logging configuration.
        
        Returns:
            logging.Logger: Configured logger
        """
        logging_config = self.config_manager.get_logging_config()
        LoggingManager.setup_logging(
            level=logging_config['level'],
            log_format=logging_config['format']
        )
        return LoggingManager.get_logger(__name__)
    
    @log_function_calls()
    def _initialize_components(self) -> None:
        """
        Initialize application components.
        
        Raises:
            ConfigurationError: If component initialization fails
        """
        try:
            # Initialize Prometheus client
            prometheus_config = self.config_manager.get_prometheus_config()
            prometheus_url = prometheus_config.get('url')
            
            if not prometheus_url:
                raise ConfigurationError("Prometheus URL not configured")
            
            self.prometheus_client = PrometheusClient(prometheus_url)
            self.logger.info(f"Initialized Prometheus client with URL: {prometheus_url}")
            
            # Initialize Policy Manager
            self.policy_manager = PolicyManager(
                self.config_manager.config, 
                self.prometheus_client
            )
            self.logger.info("Initialized Policy Manager")
            
            # Initialize rApp Catalogue client
            self.rapp_client = rAppCatalalogueClient(self.config_manager.config_path)
            self.logger.info("Initialized rApp Catalogue client")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise ConfigurationError(f"Component initialization failed: {e}")
    
    def _setup_signal_handlers(self) -> None:
        """
        Set up signal handlers for graceful shutdown.
        """
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            if self.scheduler and self.scheduler.is_running():
                self.scheduler.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    @log_function_calls()
    def collect_metrics_and_mcc_mnc(self) -> Tuple[Dict[str, Any], int, Optional[Dict[str, str]]]:
        """
        Collect SINR metrics and MCC/MNC data from Prometheus.
        
        Returns:
            Tuple containing:
            - Dict: Organized SINR metrics
            - int: Number of distinct IMSIs
            - Dict: MCC/MNC data
            
        Raises:
            MetricsCollectionError: If metrics collection fails
        """
        if not self.prometheus_client:
            raise MetricsCollectionError("Prometheus client not initialized")
        
        try:
            self.logger.info("Starting metrics collection from Prometheus")
            metrics, mcc_mnc_data = self.prometheus_client.collect_sinr_metrics_and_mcc_mnc()
            
            imsi_count = len(metrics) if metrics else 0
            self.logger.info(f"Successfully collected metrics for {imsi_count} distinct IMSIs")
            
            if not mcc_mnc_data:
                self.logger.warning("MCC/MNC data not available in metrics")
            else:
                self.logger.info(f"Collected MCC/MNC data: {mcc_mnc_data}")
            
            return metrics, imsi_count, mcc_mnc_data
            
        except Exception as e:
            self.logger.error(f"Metrics collection failed: {e}")
            raise MetricsCollectionError(f"Failed to collect metrics: {e}")
    
    @log_function_calls()
    def transform_metrics_for_optimization(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Prometheus SINR metrics for optimization model.
        
        Args:
            metrics (Dict): Raw SINR metrics from Prometheus
            
        Returns:
            Dict: Transformed metrics for optimization
        """
        if not metrics:
            self.logger.warning("No metrics provided for transformation")
            return {"users": []}
        
        # Collect all unique gNBs and their PCIs
        gnb_pci_map = {}
        for imsi, gnb_data in metrics.items():
            for gnbid, pci_data in gnb_data.items():
                if gnbid not in gnb_pci_map:
                    gnb_pci_map[gnbid] = set()
                for pci in pci_data.keys():
                    gnb_pci_map[gnbid].add(pci)
        
        self.logger.info(f"Found gNBs and their PCIs: {gnb_pci_map}")
        
        # Log statistics
        total_measurements = sum(
            len(pci_data) 
            for gnb_data in metrics.values() 
            for pci_data in gnb_data.values()
        )
        
        self.logger.info(f"Metrics transformation statistics:")
        self.logger.info(f"  - Total IMSI-gNB-PCI measurements: {total_measurements}")
        self.logger.info(f"  - Unique IMSIs: {len(metrics)}")
        self.logger.info(f"  - Unique gNBs: {len(gnb_pci_map)}")
        
        total_pcis = sum(len(pcis) for pcis in gnb_pci_map.values())
        self.logger.info(f"  - Total PCIs across all gNBs: {total_pcis}")
        
        transformed_users = []
        
        # Transform metrics to optimization format
        for imsi, gnb_data in metrics.items():
            for gnbid, pci_data in gnb_data.items():
                available_pcis = gnb_pci_map.get(gnbid, set())
                
                for pci in available_pcis:
                    if pci in pci_data:
                        sinr_value = pci_data[pci]
                    else:
                        # Estimate SINR with penalty for unmeasured PCIs
                        best_sinr = max(pci_data.values()) if pci_data else 50
                        import random
                        penalty_factor = 0.6 + random.uniform(0, 0.2)
                        sinr_value = best_sinr * penalty_factor
                    
                    user_entry = {
                        "IMSI": imsi,
                        "nodebid": gnbid,
                        "pci": pci,
                        "sinr": sinr_value,
                        "rrc_state": 1,
                        "rsrp": -60,
                        "rsrq": 1
                    }
                    transformed_users.append(user_entry)
        
        self.logger.info(f"Transformed {len(transformed_users)} user entries for optimization")
        return {"users": transformed_users}
    
    @log_function_calls()
    def run_energy_optimization(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the energy optimization algorithm.
        
        Args:
            metrics (Dict): SINR metrics from Prometheus
            
        Returns:
            Dict: Optimization solution
            
        Raises:
            OptimizationError: If optimization fails
        """
        try:
            from optimal_model.run_model import run_optimization
            
            transformed_input = self.transform_metrics_for_optimization(metrics)
            
            if not transformed_input["users"]:
                self.logger.error("No users found in metrics for optimization")
                return {"Users admission": [], "GNB_config": []}
            
            self.logger.info(f"Running optimization with {len(transformed_input['users'])} user entries")
            
            optimization_result = run_optimization(transformed_input)
            self.logger.info("Energy optimization completed successfully")
            
            # Log optimization results summary
            users_admission = optimization_result.get('Users admission', [])
            gnb_config = optimization_result.get('GNB_config', [])
            
            self.logger.info(f"Optimization results summary:")
            self.logger.info(f"  - Users admitted: {len(users_admission)}")
            self.logger.info(f"  - GNB configurations: {len(gnb_config)}")
            
            return optimization_result
            
        except Exception as e:
            self.logger.error(f"Energy optimization failed: {e}")
            raise OptimizationError(f"Optimization process failed: {e}")
    
    @log_function_calls()
    def register_with_catalogue(self) -> bool:
        """
        Register the application with the rApp catalogue.
        
        Returns:
            bool: True if registration successful, False otherwise
            
        Raises:
            RAppRegistrationError: If registration fails
        """
        if not self.rapp_client:
            raise RAppRegistrationError("rApp catalogue client not initialized")
        
        try:
            self.logger.info("Registering service with rApp catalogue")
            success = self.rapp_client.register_service()
            
            if success:
                self.logger.info("Service successfully registered with rApp catalogue")
            else:
                self.logger.error("Failed to register service with rApp catalogue")
            
            return success
            
        except Exception as e:
            self.logger.error(f"rApp catalogue registration error: {e}")
            raise RAppRegistrationError(f"Registration failed: {e}")
    
    @log_function_calls()
    def deploy_policy(self, optimization_result: Dict[str, Any], mcc_mnc_data: Optional[Dict[str, str]]) -> bool:
        """
        Deploy the optimization result as a policy instance with O1 interface support.
        
        Args:
            optimization_result (Dict): Result from energy optimization
            mcc_mnc_data (Dict, optional): MCC/MNC data for policy creation
            
        Returns:
            bool: True if deployment successful, False otherwise
        """
        if not self.policy_manager:
            self.logger.error("Policy manager not initialized")
            return False
        
        try:
            self.logger.info("Deploying optimization result with O1 interface integration")
            
            # Use the new O1-enabled deployment method
            deployment_success = self.policy_manager.deploy_optimization_with_o1(
                optimization_result, 
                mcc_mnc_data
            )
            
            if deployment_success:
                gnb_config = optimization_result.get('GNB_config', [])
                users_admission = optimization_result.get('Users admission', [])
                
                self.logger.info(f"Optimization deployment completed successfully:")
                self.logger.info(f"  - Users admitted: {len(users_admission)}")
                self.logger.info(f"  - gNBs configured: {len(gnb_config)}")
                
                # Log antenna status after deployment
                sleep(1)  # Allow time for policy to apply
                antenna_status = self.policy_manager.get_current_antenna_status()
                if antenna_status:
                    active_antennas = [ant for ant in antenna_status if ant.get('gain', 0) > 0]
                    self.logger.info(f"  - Active antennas: {len(active_antennas)}/{len(antenna_status)}")
            else:
                self.logger.error("Optimization deployment failed")
            
            return deployment_success
            
        except Exception as e:
            self.logger.error(f"Policy deployment error: {e}")
            return False
    
    @log_function_calls()
    def run_single_optimization(self) -> int:
        """
        Execute a single optimization cycle.
        
        Returns:
            int: Exit code (0 for success, 1 for failure)
        """
        try:
            self.logger.info("Starting single optimization cycle")
            
            # Step 1: Collect metrics and MCC/MNC data
            metrics, imsi_count, mcc_mnc_data = self.collect_metrics_and_mcc_mnc()
            
            self.logger.info(f"Collected metrics for {imsi_count} IMSIs")
            
            # Step 2: Run energy optimization
            optimization_result = self.run_energy_optimization(metrics)
            
            # Step 3: Deploy policy
            deployment_success = self.deploy_policy(optimization_result, mcc_mnc_data)
            
            if deployment_success:
                self.logger.info("Single optimization cycle completed successfully")
                return 0
            else:
                self.logger.error("Single optimization cycle completed with policy deployment failure")
                return 1
                
        except Exception as e:
            self.logger.error(f"Single optimization cycle failed with exception: {e}")
            return 1
    
    @log_function_calls()
    def run(self) -> int:
        """
        Execute the main application workflow with scheduling support.
        
        Returns:
            int: Exit code (0 for success, 1 for failure)
        """
        try:
            self.logger.info(f"Starting {APPLICATION_NAME} main workflow")
            
            # Register with rApp catalogue first
            if not self.register_with_catalogue():
                self.logger.error("Application startup failed at rApp registration")
                return 1
            
            # Get scheduler configuration
            scheduler_config = self.config_manager.get_scheduler_config()
            interval_minutes = scheduler_config['interval_minutes']
            run_on_startup = scheduler_config['run_on_startup']
            
            if interval_minutes <= 0:
                # Single run mode
                self.logger.info("Running in single execution mode")
                return self.run_single_optimization()
            else:
                # Scheduled mode
                self.logger.info(f"Running in scheduled mode with {interval_minutes}-minute intervals")
                
                # Initialize scheduler
                self.scheduler = FixedIntervalScheduler(
                    interval_minutes=interval_minutes,
                    task_function=self.run_single_optimization
                )
                
                # Start scheduler
                self.scheduler.start(run_immediately=run_on_startup)
                
                if self.scheduler.is_running():
                    self.logger.info("Scheduler started successfully, application will run continuously")
                    
                    try:
                        # Keep the main thread alive while scheduler runs
                        while self.scheduler.is_running():
                            sleep(1)
                    except KeyboardInterrupt:
                        self.logger.info("Application interrupted by user")
                    finally:
                        self.scheduler.stop()
                    
                    return 0
                else:
                    self.logger.error("Failed to start scheduler")
                    return 1
                
        except Exception as e:
            self.logger.error(f"{APPLICATION_NAME} failed with exception: {e}")
            if self.scheduler and self.scheduler.is_running():
                self.scheduler.stop()
            return 1


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments for the Energy Saver rApp.

    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(
        description=f'{APPLICATION_NAME} - Optimize energy consumption of E2Nodes with scheduled execution',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '-c', '--config',
        type=str,
        default=DEFAULT_CONFIG_FILE_PATH,
        help='Path to the configuration file'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'{APPLICATION_NAME} {APPLICATION_VERSION}'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Override logging level from configuration'
    )
    
    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the Energy Saver rApp application.
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    try:
        # Parse command line arguments
        args = parse_arguments()
        
        # Validate configuration file exists
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Error: Configuration file not found: {config_path}")
            return 1
        
        # Create and run the application
        app = EnergySaverApplication(str(config_path))
        
        # Override log level if specified
        if args.log_level:
            logging.getLogger().setLevel(getattr(logging, args.log_level))
        
        return app.run()
        
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        return 1
    except Exception as e:
        print(f"Application failed with error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())