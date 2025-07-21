"""
O1 Interface Client for Energy Saver rApp.

This module handles communication with the E2 simulator via O1 interface
to configure gNB antenna power settings based on optimization results.
"""

import json
import time
import logging
import requests
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urljoin

from utils.logging_manager import LoggingManager, log_function_calls
from utils.exceptions import ConfigurationError


class O1InterfaceClient:
    """
    Client for interacting with E2 simulator via O1 interface.
    
    This class manages gNB antenna power configuration through RESTconf API,
    implementing the energy optimization policies by adjusting transmission gains.
    
    Note:
        Power values in dBm from optimization results are used directly as gain values
        for the O1 interface (gain = power in dBm).
    """
    
    def __init__(self, base_url: str, timeout: int = 30):
        """
        Initialize O1 Interface Client.
        
        Args:
            base_url (str): Base URL of the E2 simulator O1 interface
            timeout (int): Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.logger = LoggingManager.get_logger(__name__)
        
        # O1 API endpoints
        self.tx_gain_endpoint = f"{self.base_url}/restconf/operations/tx-gain"
        
        self.logger.info(f"O1 Interface Client initialized with base URL: {self.base_url}")
    
    @log_function_calls()
    def get_current_antenna_gains(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get current transmission gains for all antennas.
        
        Returns:
            List[Dict]: List of antenna configurations with PCI and gain
            Format: [{"gain": 20, "pci": 7}, ...]
            None if request fails
        """
        try:
            self.logger.info("Fetching current antenna gains from E2 simulator")
            
            response = requests.get(
                self.tx_gain_endpoint,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                gains = response.json()
                self.logger.info(f"Successfully retrieved gains for {len(gains)} antennas")
                self.logger.debug(f"Current antenna gains: {gains}")
                return gains
            else:
                self.logger.error(f"Failed to get antenna gains. Status: {response.status_code}, Response: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed while getting antenna gains: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting antenna gains: {e}")
            return None
    
    @log_function_calls()
    def set_antenna_gain(self, pci: int, gain: float) -> bool:
        """
        Set transmission gain for a specific antenna.
        
        Args:
            pci (int): Physical Cell ID
            gain (float): Transmission gain value in dBm (0 to disable)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            payload = {
                "pci": pci,
                "gain": gain
            }
            
            self.logger.info(f"Setting antenna gain for PCI {pci} to {gain}")
            
            response = requests.post(
                self.tx_gain_endpoint,
                json=payload,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 204:
                self.logger.info(f"Successfully set PCI {pci} gain to {gain}")
                return True
            else:
                self.logger.error(f"Failed to set antenna gain. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed while setting antenna gain: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error setting antenna gain: {e}")
            return False
    
    @log_function_calls()
    def apply_gnb_configuration(self, gnb_config: List[Dict[str, Any]], enable_only: bool = False) -> bool:
        """
        Apply gNB configuration from optimization result.
        
        Args:
            gnb_config (List[Dict]): GNB_config section from optimization result
            enable_only (bool): If True, only enable/increase power. If False, also disable unused PCIs
            
        Returns:
            bool: True if all configurations applied successfully
            
        Note:
            Power values in dBm from optimization result are used directly as gain values for O1 interface.
        """
        if not gnb_config:
            self.logger.warning("No gNB configuration provided")
            return True
        
        success_count = 0
        total_operations = 0
        
        try:
            self.logger.info(f"Applying gNB configuration for {len(gnb_config)} gNBs (enable_only={enable_only})")
            
            for gnb in gnb_config:
                gnb_id = gnb.get('gnb', 'unknown')
                gnb_status = gnb.get('status', 'unknown')
                all_pcis = gnb.get('all_pcis', [])
                
                self.logger.info(f"Processing gNB {gnb_id} with status '{gnb_status}' and {len(all_pcis)} PCIs")
                
                for pci_config in all_pcis:
                    pci = pci_config.get('pci')
                    pci_status = pci_config.get('status', 'unknown')
                    radio_power = pci_config.get('radioPower (dBm)')
                    
                    if pci is None:
                        self.logger.warning(f"PCI missing in configuration: {pci_config}")
                        continue
                    
                    try:
                        pci_int = int(pci)
                    except (ValueError, TypeError):
                        self.logger.warning(f"Invalid PCI value: {pci}")
                        continue
                    
                    total_operations += 1
                    
                    if pci_status == 'active' and radio_power is not None:
                        # Enable/increase power for active PCIs (gain = power in dBm)
                        if self.set_antenna_gain(pci_int, radio_power):
                            success_count += 1
                            self.logger.info(f"Enabled PCI {pci_int} with gain {radio_power} dBm")
                        else:
                            self.logger.error(f"Failed to enable PCI {pci_int}")
                    
                    elif pci_status == 'powered_off' and not enable_only:
                        # Disable PCIs that should be powered off (only if enable_only=False)
                        if self.set_antenna_gain(pci_int, 0.0):
                            success_count += 1
                            self.logger.info(f"Disabled PCI {pci_int} (set gain to 0)")
                        else:
                            self.logger.error(f"Failed to disable PCI {pci_int}")
                    
                    elif enable_only and pci_status == 'powered_off':
                        # Skip disabling when enable_only=True
                        self.logger.debug(f"Skipping PCI {pci_int} disable (enable_only mode)")
                        total_operations -= 1  # Don't count skipped operations
            
            success_rate = (success_count / total_operations * 100) if total_operations > 0 else 100
            self.logger.info(f"gNB configuration completed: {success_count}/{total_operations} operations successful ({success_rate:.1f}%)")
            
            return success_count == total_operations
            
        except Exception as e:
            self.logger.error(f"Error applying gNB configuration: {e}")
            return False
    
    @log_function_calls()
    def backup_current_configuration(self) -> Optional[List[Dict[str, Any]]]:
        """
        Backup current antenna configuration for potential rollback.
        
        Returns:
            List[Dict]: Current antenna gains or None if backup fails
        """
        self.logger.info("Creating backup of current antenna configuration")
        return self.get_current_antenna_gains()
    
    @log_function_calls()
    def restore_configuration(self, backup_config: List[Dict[str, Any]]) -> bool:
        """
        Restore antenna configuration from backup.
        
        Args:
            backup_config (List[Dict]): Backup configuration to restore
            
        Returns:
            bool: True if restoration successful
        """
        if not backup_config:
            self.logger.warning("No backup configuration provided for restoration")
            return False
        
        self.logger.info(f"Restoring antenna configuration from backup ({len(backup_config)} antennas)")
        
        success_count = 0
        for antenna in backup_config:
            pci = antenna.get('pci')
            gain = antenna.get('gain')
            
            if pci is not None and gain is not None:
                if self.set_antenna_gain(pci, gain):
                    success_count += 1
                else:
                    self.logger.error(f"Failed to restore PCI {pci} to gain {gain}")
        
        success_rate = (success_count / len(backup_config) * 100) if backup_config else 100
        self.logger.info(f"Configuration restoration completed: {success_count}/{len(backup_config)} successful ({success_rate:.1f}%)")
        
        return success_count == len(backup_config)
    
    @log_function_calls()
    def disable_all_antennas(self) -> bool:
        """
        Disable all antennas by setting their gain to 0.
        
        Returns:
            bool: True if all antennas disabled successfully
        """
        current_gains = self.get_current_antenna_gains()
        if not current_gains:
            self.logger.error("Cannot disable antennas - failed to get current configuration")
            return False
        
        self.logger.info(f"Disabling all {len(current_gains)} antennas")
        
        success_count = 0
        for antenna in current_gains:
            pci = antenna.get('pci')
            if pci is not None:
                if self.set_antenna_gain(pci, 0.0):
                    success_count += 1
        
        success_rate = (success_count / len(current_gains) * 100) if current_gains else 100
        self.logger.info(f"Antenna shutdown completed: {success_count}/{len(current_gains)} successful ({success_rate:.1f}%)")
        
        return success_count == len(current_gains)
