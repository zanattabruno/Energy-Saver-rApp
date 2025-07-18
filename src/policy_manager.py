"""
Policy Manager Module for Energy Saver rApp

This module handles the creation, parsing, and deployment of A1 policy instances
for the Energy Saver rApp application.
"""

import json
import time
import logging
import requests
from prometheus_metrics_collector import PrometheusClient


class PolicyManager:
    """
    Manages A1 policy instances for the Energy Saver application.
    """
    
    def __init__(self, config, prometheus_client=None):
        """
        Initialize the PolicyManager with configuration.
        
        Args:
            config (dict): Configuration dictionary
            prometheus_client (PrometheusClient, optional): Prometheus client for fetching MCC/MNC
        """
        self.config = config
        self.prometheus_client = prometheus_client
        self.logger = logging.getLogger(__name__)
    
    def parse_optimization_to_policy(self, optimization_result):
        """
        Parse optimization result into A1 policy instance format.
        
        Args:
            optimization_result (dict): Result from energy optimization containing Users admission and GNB_config
        
        Returns:
            dict: A1 policy instance in the format expected by the Near-RT RIC
        """
        self.logger.info("Parsing optimization result to A1 policy instance format")
        
        # Get MCC and MNC from Prometheus metrics - required for policy creation
        mcc_mnc_data = None
        if self.prometheus_client:
            mcc_mnc_data = self.prometheus_client.collect_mcc_mnc_from_metrics()
        
        if not mcc_mnc_data:
            self.logger.error("MCC and MNC information is required from Prometheus metrics but not available")
            self.logger.error("Cannot create policy instance without MCC/MNC from Prometheus")
            return None
        
        default_mcc = mcc_mnc_data['mcc']
        default_mnc = mcc_mnc_data['mnc']
        self.logger.info(f"Using MCC: {default_mcc}, MNC: {default_mnc} from Prometheus metrics")
        
        ric_id = self.config.get('policy', {}).get('ric_id', 'ric4')
        service_id = self.config.get('policy', {}).get('service_id', 'EnergySaverApp')
        policy_type_id = self.config.get('policy', {}).get('policy_type_id', '5')
        
        # Generate a unique policy ID (timestamp-based)
        policy_id = str(int(time.time()))
        
        users_admission = optimization_result.get('Users admission', [])
        
        if not users_admission:
            self.logger.warning("No users found in optimization result")
            return self._create_empty_policy_instance(ric_id, policy_id, service_id, policy_type_id)
        
        # Group users by gNB and PCI combination
        gnb_pci_groups = {}
        for user in users_admission:
            imsi = user.get('IMSI')
            gnb = user.get('gnb')
            pci = user.get('pci')
            
            if not all([imsi, gnb is not None, pci is not None]):
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
        
        # Build E2NodeList
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
        
        # Create the complete policy instance
        policy_instance = {
            "ric_id": ric_id,
            "policy_id": policy_id,
            "service_id": service_id,
            "policy_data": {
                "E2NodeList": e2_node_list
            },
            "policytype_id": policy_type_id
        }
        
        self.logger.info(f"Created policy instance with {len(e2_node_list)} E2Node entries")
        self.logger.info(f"Total users assigned: {sum(len(entry['UEList']) for entry in e2_node_list)}")
        
        return policy_instance
    
    def _create_empty_policy_instance(self, ric_id, policy_id, service_id, policy_type_id):
        """
        Create an empty policy instance structure.
        
        Args:
            ric_id (str): RIC identifier
            policy_id (str): Policy identifier
            service_id (str): Service identifier
            policy_type_id (str): Policy type identifier
        
        Returns:
            dict: Empty policy instance
        """
        return {
            "ric_id": ric_id,
            "policy_id": policy_id,
            "service_id": service_id,
            "policy_data": {
                "E2NodeList": []
            },
            "policytype_id": policy_type_id
        }
    
    def deploy_policy_instance(self, policy_instance):
        """
        Deploy the policy instance to the Near-RT RIC via A1 interface.
        
        Args:
            policy_instance (dict): Policy instance to deploy
        
        Returns:
            bool: True if deployment was successful, False otherwise
        """
        self.logger.info("Deploying policy instance to Near-RT RIC")
        
        # Get A1 Policy Management Service URL from config
        a1_pms_url = self.config.get('nonrtric', {}).get('base_url_pms')
        if not a1_pms_url:
            self.logger.error("A1 Policy Management Service URL not configured")
            return False
        
        # Construct the full URL for policy deployment
        policy_url = f"{a1_pms_url}/policies"
        
        try:
            # Send PUT request to deploy the policy
            response = requests.put(
                policy_url,
                json=policy_instance,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                self.logger.info(f"Policy instance successfully deployed. Policy ID: {policy_instance.get('policy_id')}")
                self.logger.info(f"Response: {response.text}")
                return True
            else:
                self.logger.error(f"Failed to deploy policy instance. Status code: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error deploying policy instance: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during policy deployment: {e}")
            return False
    
    def delete_policy_instance(self, policy_id):
        """
        Delete a policy instance from the Near-RT RIC.
        
        Args:
            policy_id (str): ID of the policy to delete
        
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        self.logger.info(f"Deleting policy instance with ID: {policy_id}")
        
        # Get A1 Policy Management Service URL from config
        a1_pms_url = self.config.get('nonrtric', {}).get('base_url_pms')
        if not a1_pms_url:
            self.logger.error("A1 Policy Management Service URL not configured")
            return False
        
        # Construct the full URL for policy deletion
        policy_url = f"{a1_pms_url}/policies/{policy_id}"
        
        try:
            # Send DELETE request to remove the policy
            response = requests.delete(
                policy_url,
                timeout=30
            )
            
            if response.status_code in [200, 204]:
                self.logger.info(f"Policy instance successfully deleted. Policy ID: {policy_id}")
                return True
            else:
                self.logger.error(f"Failed to delete policy instance. Status code: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error deleting policy instance: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during policy deletion: {e}")
            return False
    
    def save_policy_instance(self, policy_instance, file_path):
        """
        Save policy instance to a JSON file.
        
        Args:
            policy_instance (dict): Policy instance to save
            file_path (str): Path to save the file
        
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            with open(file_path, 'w') as f:
                json.dump(policy_instance, f, indent=4)
            self.logger.info(f"Policy instance saved to {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save policy instance to {file_path}: {e}")
            return False
    
    def load_policy_instance(self, file_path):
        """
        Load policy instance from a JSON file.
        
        Args:
            file_path (str): Path to load the file from
        
        Returns:
            dict or None: Policy instance if successful, None otherwise
        """
        try:
            with open(file_path, 'r') as f:
                policy_instance = json.load(f)
            self.logger.info(f"Policy instance loaded from {file_path}")
            return policy_instance
        except Exception as e:
            self.logger.error(f"Failed to load policy instance from {file_path}: {e}")
            return None
