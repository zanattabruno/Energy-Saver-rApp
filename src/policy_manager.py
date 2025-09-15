"""
Policy Manager Module for Energy Saver rApp.

This module handles the creation, parsing, validation, and deployment of A1 policy instances
for the Energy Saver rApp application with comprehensive error handling and logging.
"""

import json
import time
import logging
import requests
from typing import Dict, Any, List, Optional
from pathlib import Path

from utils.logging_manager import LoggingManager, log_function_calls
from utils.exceptions import PolicyDeploymentError, ConfigurationError
from o1_interface_client import O1InterfaceClient


class PolicyManager:
    """
    Advanced policy manager for A1 policy instances in the Energy Saver application.
    
    This class provides comprehensive policy lifecycle management including creation,
    validation, deployment, monitoring, and cleanup operations.
    """
    
    def __init__(self, config: Dict[str, Any], prometheus_client=None):
        """
        Initialize the PolicyManager with configuration and optional Prometheus client.
        
        Args:
            config (Dict[str, Any]): Application configuration dictionary
            prometheus_client: Optional Prometheus client for fetching MCC/MNC data
            
        Raises:
            ConfigurationError: If required configuration is missing
        """
        self.config = config
        self.prometheus_client = prometheus_client
        self.logger = LoggingManager.get_logger(__name__)
        
        # Initialize O1 interface client
        self.o1_client = None
        self._initialize_o1_client()
        
        # Validate and extract configuration
        self._validate_configuration()
        self._extract_policy_config()
        
        self.logger.info("Policy Manager initialized successfully")
    
    def _validate_configuration(self) -> None:
        """
        Validate that required configuration sections are present.
        
        Raises:
            ConfigurationError: If required configuration is missing
        """
        required_sections = ['policy', 'nonrtric']
        required_keys = {
            'policy': ['ric_id', 'service_id', 'policy_type_id'],
            'nonrtric': ['base_url_pms']
        }
        
        for section in required_sections:
            if section not in self.config:
                raise ConfigurationError(f"Missing required configuration section: {section}")
            
            for key in required_keys.get(section, []):
                if key not in self.config[section]:
                    raise ConfigurationError(f"Missing required configuration key: {section}.{key}")
        
        self.logger.debug("Policy Manager configuration validation completed")
    
    def _extract_policy_config(self) -> None:
        """Extract and store policy-related configuration."""
        policy_config = self.config.get('policy', {})
        
        self.default_ric_id = policy_config.get('ric_id', 'ric4')
        self.default_service_id = policy_config.get('service_id', 'EnergySaverApp')
        self.default_policy_type_id = policy_config.get('policy_type_id', '5')
        
        # A1 PMS configuration
        nonrtric_config = self.config.get('nonrtric', {})
        self.a1_pms_url = nonrtric_config.get('base_url_pms')
        
        self.logger.debug(f"Policy configuration: RIC={self.default_ric_id}, "
                         f"Service={self.default_service_id}, Type={self.default_policy_type_id}")
    
    def _initialize_o1_client(self) -> None:
        """Initialize O1 interface client for E2 simulator communication."""
        try:
            o1_config = self.config.get('o1_interface', {})
            o1_base_url = o1_config.get('base_url', 'http://e2sim-addr:8090')
            o1_timeout = o1_config.get('timeout', 30)
            
            self.o1_client = O1InterfaceClient(o1_base_url, o1_timeout)
            self.logger.info(f"O1 interface client initialized with URL: {o1_base_url}")
            
        except Exception as e:
            self.logger.warning(f"Failed to initialize O1 interface client: {e}")
            self.logger.warning("O1 interface features will be disabled")
            self.o1_client = None
    
    @log_function_calls()
    def parse_optimization_to_policy(
        self, 
        optimization_result: Dict[str, Any], 
        mcc_mnc_data: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Parse optimization result into A1 policy instance format with comprehensive validation.
        
        Args:
            optimization_result (Dict[str, Any]): Result from energy optimization containing
                                                 Users admission and GNB_config
            mcc_mnc_data (Dict[str, str], optional): Pre-fetched MCC/MNC data to avoid 
                                                   additional Prometheus calls
        
        Returns:
            Optional[Dict[str, Any]]: A1 policy instance in the format expected by the Near-RT RIC,
                                    or None if creation fails
        """
        self.logger.info("Starting policy instance creation from optimization result")
        
        # Validate inputs
        if not self._validate_optimization_result(optimization_result):
            return None
        
        if not self._validate_mcc_mnc_data(mcc_mnc_data):
            return None
        
        # Extract default MCC/MNC values
        default_mcc = mcc_mnc_data['mcc']
        default_mnc = mcc_mnc_data['mnc']
        self.logger.info(f"Using MCC: {default_mcc}, MNC: {default_mnc} from pre-fetched data")
        
        # Generate unique policy ID
        policy_id = self._generate_policy_id()
        
        # Process users admission data
        users_admission = optimization_result.get('Users admission', [])
        
        if not users_admission:
            self.logger.warning("No users found in optimization result - creating empty policy")
            return self._create_empty_policy_instance(policy_id)
        
        # Group users by gNB and PCI combination
        gnb_pci_groups = self._group_users_by_gnb_pci(users_admission)
        
        if not gnb_pci_groups:
            self.logger.warning("No valid user groups found - creating empty policy")
            return self._create_empty_policy_instance(policy_id)
        
        # Build E2NodeList
        e2_node_list = self._build_e2_node_list(gnb_pci_groups, default_mcc, default_mnc)
        
        # Create the complete policy instance
        policy_instance = self._create_policy_instance(policy_id, e2_node_list)
        
        # Log creation summary
        self._log_policy_creation_summary(policy_instance, e2_node_list)
        
        return policy_instance
    
    def _validate_optimization_result(self, optimization_result: Dict[str, Any]) -> bool:
        """
        Validate the optimization result structure.
        
        Args:
            optimization_result: Optimization result to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not optimization_result:
            self.logger.error("Optimization result is empty")
            return False
        
        if not isinstance(optimization_result, dict):
            self.logger.error("Optimization result is not a dictionary")
            return False
        
        # Check for required keys
        if 'Users admission' not in optimization_result:
            self.logger.error("'Users admission' key missing from optimization result")
            return False
        
        self.logger.debug("Optimization result validation passed")
        return True
    
    def _validate_mcc_mnc_data(self, mcc_mnc_data: Optional[Dict[str, str]]) -> bool:
        """
        Validate MCC/MNC data.
        
        Args:
            mcc_mnc_data: MCC/MNC data to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not mcc_mnc_data:
            self.logger.error("MCC/MNC data is required but not provided")
            self.logger.error("Please ensure MCC/MNC data is collected during SINR metrics collection")
            return False
        
        if 'mcc' not in mcc_mnc_data or 'mnc' not in mcc_mnc_data:
            self.logger.error("MCC/MNC data is incomplete - missing 'mcc' or 'mnc' keys")
            return False
        
        # Validate MCC/MNC format
        mcc = str(mcc_mnc_data['mcc'])
        mnc = str(mcc_mnc_data['mnc'])
        
        if not mcc.isdigit() or not mnc.isdigit():
            self.logger.error(f"Invalid MCC/MNC format - MCC: {mcc}, MNC: {mnc}")
            return False
        
        if len(mcc) != 3 or len(mnc) not in [2, 3]:
            self.logger.warning(f"Unusual MCC/MNC length - MCC: {mcc} ({len(mcc)} digits), "
                              f"MNC: {mnc} ({len(mnc)} digits)")
        
        self.logger.debug("MCC/MNC data validation passed")
        return True
    
    def _generate_policy_id(self) -> str:
        """
        Generate a unique policy ID based on timestamp.
        
        Returns:
            str: Unique policy ID
        """
        policy_id = str(int(time.time()))
        self.logger.debug(f"Generated policy ID: {policy_id}")
        return policy_id
    
    def _group_users_by_gnb_pci(self, users_admission: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Group users by gNB and PCI combination.
        
        Args:
            users_admission: List of user admission data
            
        Returns:
            Dict: Grouped users by gNB-PCI combination
        """
        gnb_pci_groups = {}
        invalid_entries = 0
        
        for user in users_admission:
            imsi = user.get('IMSI')
            gnb = user.get('gnb')
            pci = user.get('pci')
            
            if not all([imsi, gnb is not None, pci is not None]):
                invalid_entries += 1
                self.logger.warning(f"Incomplete user admission data: {user}")
                continue
            
            # Create a key for grouping (gnb_pci)
            gnb_pci_key = f"{gnb}_{pci}"
            
            if gnb_pci_key not in gnb_pci_groups:
                gnb_pci_groups[gnb_pci_key] = {
                    'gnbid': str(gnb),
                    'pci': str(pci),
                    'imsis': []
                }
            
            gnb_pci_groups[gnb_pci_key]['imsis'].append(imsi)
        
        if invalid_entries > 0:
            self.logger.warning(f"Skipped {invalid_entries} invalid user admission entries")
        
        self.logger.info(f"Grouped users into {len(gnb_pci_groups)} gNB-PCI combinations")
        return gnb_pci_groups
    
    def _build_e2_node_list(
        self, 
        gnb_pci_groups: Dict[str, Dict[str, Any]], 
        default_mcc: str, 
        default_mnc: str
    ) -> List[Dict[str, Any]]:
        """
        Build the E2NodeList from grouped user data.
        
        Args:
            gnb_pci_groups: Grouped users by gNB-PCI
            default_mcc: Default MCC value
            default_mnc: Default MNC value
            
        Returns:
            List[Dict[str, Any]]: E2NodeList for the policy instance
        """
        e2_node_list = []
        
        for gnb_pci_key, group_data in gnb_pci_groups.items():
            # Create UEList for this gNB-PCI combination
            ue_list = [{"imsi": imsi} for imsi in group_data['imsis']]
            
            e2_node_entry = {
                "mcc": default_mcc,
                "mnc": default_mnc,
                "gnbid": group_data['gnbid'],
                "pci": group_data['pci'],
                "UEList": ue_list
            }
            
            e2_node_list.append(e2_node_entry)
            self.logger.debug(f"Added E2Node entry for gNB {group_data['gnbid']}, PCI {group_data['pci']} "
                            f"with {len(ue_list)} users")
        
        return e2_node_list
    
    def _create_policy_instance(self, policy_id: str, e2_node_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create the complete policy instance structure.
        
        Args:
            policy_id: Unique policy identifier
            e2_node_list: List of E2Node entries
            
        Returns:
            Dict[str, Any]: Complete policy instance
        """
        policy_instance = {
            "ric_id": self.default_ric_id,
            "policy_id": policy_id,
            "service_id": self.default_service_id,
            "policy_data": {
                "E2NodeList": e2_node_list
            },
            "policytype_id": self.default_policy_type_id
        }
        
        return policy_instance
    
    def _create_empty_policy_instance(self, policy_id: str) -> Dict[str, Any]:
        """
        Create an empty policy instance structure.
        
        Args:
            policy_id: Unique policy identifier
        
        Returns:
            Dict[str, Any]: Empty policy instance
        """
        return {
            "ric_id": self.default_ric_id,
            "policy_id": policy_id,
            "service_id": self.default_service_id,
            "policy_data": {
                "E2NodeList": []
            },
            "policytype_id": self.default_policy_type_id
        }
    
    def _log_policy_creation_summary(
        self, 
        policy_instance: Dict[str, Any], 
        e2_node_list: List[Dict[str, Any]]
    ) -> None:
        """
        Log a summary of the policy creation.
        
        Args:
            policy_instance: Created policy instance
            e2_node_list: E2Node list from the policy
        """
        total_users = sum(len(entry.get('UEList', [])) for entry in e2_node_list)
        
        self.logger.info(f"Policy instance created successfully:")
        self.logger.info(f"  - Policy ID: {policy_instance.get('policy_id')}")
        self.logger.info(f"  - E2Node entries: {len(e2_node_list)}")
        self.logger.info(f"  - Total users assigned: {total_users}")
        self.logger.info(f"  - RIC ID: {policy_instance.get('ric_id')}")
        self.logger.info(f"  - Service ID: {policy_instance.get('service_id')}")
    
    @log_function_calls()
    def deploy_policy_instance(self, policy_instance: Dict[str, Any]) -> bool:
        """
        Deploy the policy instance to the Near-RT RIC via A1 interface with enhanced error handling.
        
        Args:
            policy_instance (Dict[str, Any]): Policy instance to deploy
        
        Returns:
            bool: True if deployment was successful, False otherwise
            
        Raises:
            PolicyDeploymentError: If deployment fails due to client configuration
        """
        self.logger.info("Starting policy instance deployment to Near-RT RIC")
        
        # Validate policy instance
        if not self._validate_policy_instance(policy_instance):
            return False
        
        # Validate A1 PMS configuration
        if not self.a1_pms_url:
            raise PolicyDeploymentError("A1 Policy Management Service URL not configured")
        
        # Construct the full URL for policy deployment
        policy_url = f"{self.a1_pms_url}/policies"
        policy_id = policy_instance.get('policy_id')
        
        try:
            self.logger.debug(f"Deploying policy to URL: {policy_url}")
            self.logger.debug(f"Policy payload size: {len(json.dumps(policy_instance))} bytes")
            
            # Send PUT request to deploy the policy
            response = requests.put(
                policy_url,
                json=policy_instance,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            # Handle different response codes
            if response.status_code in [200, 201]:
                self.logger.info(f"Policy instance successfully deployed - Policy ID: {policy_id}")
                self.logger.debug(f"Deployment response: {response.text}")
                return True
            elif response.status_code == 400:
                self.logger.error(f"Bad request during policy deployment - Policy ID: {policy_id}")
                self.logger.error(f"Response: {response.text}")
                return False
            elif response.status_code == 409:
                self.logger.warning(f"Policy conflict (already exists) - Policy ID: {policy_id}")
                self.logger.info("Attempting to update existing policy")
                return self._update_existing_policy(policy_instance)
            else:
                self.logger.error(f"Failed to deploy policy instance - Status: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout during policy deployment - Policy ID: {policy_id}")
            return False
        except requests.exceptions.ConnectionError:
            self.logger.error(f"Connection error during policy deployment: {self.a1_pms_url}")
            return False
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error during policy deployment: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during policy deployment: {e}")
            raise PolicyDeploymentError(f"Policy deployment failed: {e}")
    
    def _validate_policy_instance(self, policy_instance: Dict[str, Any]) -> bool:
        """
        Validate policy instance structure before deployment.
        
        Args:
            policy_instance: Policy instance to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        required_keys = ['ric_id', 'policy_id', 'service_id', 'policy_data', 'policytype_id']
        
        for key in required_keys:
            if key not in policy_instance:
                self.logger.error(f"Missing required key in policy instance: {key}")
                return False
        
        # Validate policy_data structure
        policy_data = policy_instance.get('policy_data', {})
        if 'E2NodeList' not in policy_data:
            self.logger.error("Missing E2NodeList in policy_data")
            return False
        
        e2_node_list = policy_data['E2NodeList']
        if not isinstance(e2_node_list, list):
            self.logger.error("E2NodeList must be a list")
            return False
        
        self.logger.debug("Policy instance validation passed")
        return True
    
    def _update_existing_policy(self, policy_instance: Dict[str, Any]) -> bool:
        """
        Attempt to update an existing policy.
        
        Args:
            policy_instance: Policy instance to update
            
        Returns:
            bool: True if update successful, False otherwise
        """
        policy_id = policy_instance.get('policy_id')
        policy_url = f"{self.a1_pms_url}/policies/{policy_id}"
        
        try:
            self.logger.info(f"Attempting to update existing policy: {policy_id}")
            
            response = requests.put(
                policy_url,
                json=policy_instance,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code in [200, 204]:
                self.logger.info(f"Policy successfully updated: {policy_id}")
                return True
            else:
                self.logger.error(f"Failed to update policy: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating existing policy: {e}")
            return False
    
    @log_function_calls()
    def delete_policy_instance(self, policy_id: str) -> bool:
        """
        Delete a policy instance from the Near-RT RIC with enhanced error handling.
        
        Args:
            policy_id (str): ID of the policy to delete
        
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        self.logger.info(f"Starting deletion of policy instance: {policy_id}")
        
        if not self.a1_pms_url:
            self.logger.error("A1 Policy Management Service URL not configured")
            return False
        
        # Construct the full URL for policy deletion
        policy_url = f"{self.a1_pms_url}/policies/{policy_id}"
        
        try:
            self.logger.debug(f"Sending DELETE request to: {policy_url}")
            
            # Send DELETE request to remove the policy
            response = requests.delete(policy_url, timeout=30)
            
            if response.status_code in [200, 204]:
                self.logger.info(f"Policy instance successfully deleted: {policy_id}")
                return True
            elif response.status_code == 404:
                self.logger.warning(f"Policy not found (may already be deleted): {policy_id}")
                return True  # Consider this a success
            else:
                self.logger.error(f"Failed to delete policy instance - Status: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout during policy deletion: {policy_id}")
            return False
        except requests.exceptions.ConnectionError:
            self.logger.error(f"Connection error during policy deletion: {self.a1_pms_url}")
            return False
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error during policy deletion: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during policy deletion: {e}")
            return False
    
    @log_function_calls()
    def get_policy_status(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a deployed policy instance.
        
        Args:
            policy_id (str): ID of the policy to check
        
        Returns:
            Optional[Dict[str, Any]]: Policy status information or None if not found
        """
        self.logger.debug(f"Checking status of policy instance: {policy_id}")
        
        if not self.a1_pms_url:
            self.logger.error("A1 Policy Management Service URL not configured")
            return None
        
        policy_url = f"{self.a1_pms_url}/policies/{policy_id}"
        
        try:
            response = requests.get(policy_url, timeout=30)
            
            if response.status_code == 200:
                policy_info = response.json()
                self.logger.debug(f"Policy {policy_id} found and active")
                return policy_info
            elif response.status_code == 404:
                self.logger.info(f"Policy {policy_id} not found")
                return None
            else:
                self.logger.warning(f"Unexpected response when checking policy status: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error checking policy status: {e}")
            return None
    
    @log_function_calls()
    def save_policy_instance(self, policy_instance: Dict[str, Any], file_path: str) -> bool:
        """
        Save policy instance to a JSON file with error handling.
        
        Args:
            policy_instance (Dict[str, Any]): Policy instance to save
            file_path (str): Path to save the file
        
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            # Ensure directory exists
            file_path_obj = Path(file_path)
            file_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path_obj, 'w', encoding='utf-8') as f:
                json.dump(policy_instance, f, indent=4, ensure_ascii=False)
            
            self.logger.info(f"Policy instance saved to {file_path}")
            self.logger.debug(f"File size: {file_path_obj.stat().st_size} bytes")
            return True
            
        except PermissionError:
            self.logger.error(f"Permission denied when saving to {file_path}")
            return False
        except OSError as e:
            self.logger.error(f"OS error when saving policy instance: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error saving policy instance to {file_path}: {e}")
            return False
    
    @log_function_calls()
    def load_policy_instance(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Load policy instance from a JSON file with error handling.
        
        Args:
            file_path (str): Path to load the file from
        
        Returns:
            Optional[Dict[str, Any]]: Policy instance if successful, None otherwise
        """
        try:
            file_path_obj = Path(file_path)
            
            if not file_path_obj.exists():
                self.logger.error(f"Policy file not found: {file_path}")
                return None
            
            with open(file_path_obj, 'r', encoding='utf-8') as f:
                policy_instance = json.load(f)
            
            # Validate loaded policy
            if self._validate_policy_instance(policy_instance):
                self.logger.info(f"Policy instance loaded from {file_path}")
                return policy_instance
            else:
                self.logger.error(f"Invalid policy instance in file: {file_path}")
                return None
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in policy file {file_path}: {e}")
            return None
        except PermissionError:
            self.logger.error(f"Permission denied when reading {file_path}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error loading policy instance from {file_path}: {e}")
            return None
    
    @log_function_calls()
    def list_active_policies(self) -> List[Dict[str, Any]]:
        """
        List all active policies from the A1 Policy Management Service.
        
        Returns:
            List[Dict[str, Any]]: List of active policies
        """
        self.logger.info("Retrieving list of active policies")
        
        if not self.a1_pms_url:
            self.logger.error("A1 Policy Management Service URL not configured")
            return []
        
        policies_url = f"{self.a1_pms_url}/policies"
        
        try:
            response = requests.get(policies_url, timeout=30)
            
            if response.status_code == 200:
                policies = response.json()
                if isinstance(policies, list):
                    self.logger.info(f"Found {len(policies)} active policies")
                    return policies
                else:
                    self.logger.warning("Unexpected response format for policies list")
                    return []
            else:
                self.logger.error(f"Failed to retrieve policies list: {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error retrieving active policies: {e}")
            return []
    
    @log_function_calls()
    def deploy_optimization_with_o1(
        self, 
        optimization_result: Dict[str, Any], 
        mcc_mnc_data: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Deploy optimization result using both O1 interface (power configuration) and A1 policy.

        Updated flow (requested):
        1. Apply FULL cell power configuration first (enable active cells, disable/power off inactive ones)
        2. Deploy A1 policy (handover / UE admission logic)
        
        Args:
            optimization_result (Dict[str, Any]): Result from energy optimization
            mcc_mnc_data (Dict[str, str], optional): MCC/MNC data for policy creation
            
        Returns:
            bool: True if deployment successful, False otherwise
        """
        if not self.o1_client:
            self.logger.warning("O1 interface not available, falling back to A1 policy only")
            return self.deploy_policy_instance_from_optimization(optimization_result, mcc_mnc_data)
        
        try:
            self.logger.info("Starting optimization deployment (power first, then policy)")

            # Extract gNB configuration
            gnb_config = optimization_result.get('GNB_config', [])
            if not gnb_config:
                self.logger.warning("No GNB configuration in optimization result")
                return False
            
            # Step 1: Backup current configuration
            self.logger.info("Step 1: Backing up current antenna configuration")
            backup_config = self.o1_client.backup_current_configuration()
            if not backup_config:
                self.logger.error("Failed to backup current configuration")
                return False
            
            # Step 2: Apply full antenna power configuration (enable & disable in one pass)
            self.logger.info("Step 2: Applying full antenna power configuration (enable + disable)")
            full_apply_success = self.o1_client.apply_gnb_configuration(gnb_config, enable_only=False)
            if not full_apply_success:
                self.logger.error("Failed to apply full antenna power configuration - attempting rollback")
                self.o1_client.restore_configuration(backup_config)
                return False

            # Step 3: Deploy A1 policy instance (handover/admission)
            self.logger.info("Step 3: Deploying A1 policy instance (handover)")
            policy_success = self.deploy_policy_instance_from_optimization(optimization_result, mcc_mnc_data)
            if not policy_success:
                self.logger.error("Failed to deploy A1 policy - attempting rollback of antenna config")
                self.o1_client.restore_configuration(backup_config)
                return False

            self.logger.info("Optimization deployment completed successfully (power then policy)")
            return True
            
        except Exception as e:
            self.logger.error(f"Error in O1-based deployment: {e}")
            # Attempt to restore backup if available
            if 'backup_config' in locals() and backup_config:
                self.logger.info("Attempting to restore backup configuration due to deployment failure")
                self.o1_client.restore_configuration(backup_config)
            return False
    
    @log_function_calls()
    def deploy_policy_instance_from_optimization(
        self, 
        optimization_result: Dict[str, Any], 
        mcc_mnc_data: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Create and deploy A1 policy instance from optimization result.
        
        Args:
            optimization_result (Dict[str, Any]): Result from energy optimization
            mcc_mnc_data (Dict[str, str], optional): MCC/MNC data for policy creation
            
        Returns:
            bool: True if deployment successful, False otherwise
        """
        try:
            # Create policy instance
            policy_instance = self.parse_optimization_to_policy(optimization_result, mcc_mnc_data)
            if not policy_instance:
                self.logger.error("Failed to create policy instance from optimization result")
                return False
            
            # Deploy the policy
            return self.deploy_policy_instance(policy_instance)
            
        except Exception as e:
            self.logger.error(f"Error deploying policy from optimization result: {e}")
            return False
    
    @log_function_calls()
    def apply_gnb_power_configuration(self, gnb_config: List[Dict[str, Any]]) -> bool:
        """
        Apply gNB power configuration via O1 interface.
        
        Args:
            gnb_config (List[Dict]): GNB_config from optimization result
            
        Returns:
            bool: True if configuration applied successfully
        """
        if not self.o1_client:
            self.logger.error("O1 interface client not available")
            return False
        
        return self.o1_client.apply_gnb_configuration(gnb_config)
    
    @log_function_calls()
    def shutdown_all_antennas(self) -> bool:
        """
        Emergency shutdown of all antennas via O1 interface.
        
        Returns:
            bool: True if all antennas disabled successfully
        """
        if not self.o1_client:
            self.logger.error("O1 interface client not available")
            return False
        
        self.logger.warning("Initiating emergency shutdown of all antennas")
        return self.o1_client.disable_all_antennas()
    
    @log_function_calls()
    def get_current_antenna_status(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get current antenna status from E2 simulator.
        
        Returns:
            List[Dict]: Current antenna gains or None if unavailable
        """
        if not self.o1_client:
            self.logger.error("O1 interface client not available")
            return None
        
        return self.o1_client.get_current_antenna_gains()
