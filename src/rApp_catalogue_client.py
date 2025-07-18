"""
rApp Catalogue Client for Energy Saver rApp.

This module provides a client for registering services with the rApp Catalogue.
"""

import logging
import requests
from typing import Dict, Any, Optional
from pathlib import Path

from utils.config_manager import ConfigManager
from utils.logging_manager import LoggingManager, log_function_calls
from utils.exceptions import RAppRegistrationError


class RAppCatalogueClient:
    """
    A client for registering and managing services with the rApp Catalogue.
    
    This class handles service registration, including validation and error handling.
    """

    def __init__(self, config_source):
        """
        Initialize the rApp Catalogue client.

        Args:
            config_source: Either a configuration file path (str) or a config dictionary
            
        Raises:
            RAppRegistrationError: If configuration is invalid
        """
        self.logger = LoggingManager.get_logger(__name__)
        
        # Handle both file path and config dict for backward compatibility
        if isinstance(config_source, (str, Path)):
            self.config_manager = ConfigManager(str(config_source))
            self.config = self.config_manager.config
        else:
            self.config = config_source
            
        self._validate_configuration()
        self._extract_service_info()
        
        self.logger.info("rApp Catalogue client initialized successfully")

    def _validate_configuration(self) -> None:
        """
        Validate that required configuration is present.
        
        Raises:
            RAppRegistrationError: If required configuration is missing
        """
        required_keys = [
            'nonrtric.base_url_rApp_catalogue',
            'nonrtric.service_name',
            'nonrtric.service_version',
            'nonrtric.service_display_name',
            'nonrtric.service_description'
        ]
        
        for key_path in required_keys:
            if self._get_config_value(key_path) is None:
                raise RAppRegistrationError(f"Missing required configuration: {key_path}")
    
    def _get_config_value(self, key_path: str) -> Optional[str]:
        """
        Get configuration value using dot notation.
        
        Args:
            key_path (str): Dot-separated path to the configuration key
            
        Returns:
            Optional[str]: Configuration value or None if not found
        """
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return None
    
    def _extract_service_info(self) -> None:
        """Extract service information from configuration."""
        self.base_url = self._get_config_value('nonrtric.base_url_rApp_catalogue')
        self.service_name = self._get_config_value('nonrtric.service_name')
        self.version = self._get_config_value('nonrtric.service_version')
        self.display_name = self._get_config_value('nonrtric.service_display_name')
        self.description = self._get_config_value('nonrtric.service_description')
        
        self.logger.debug(f"Service configuration extracted: {self.service_name} v{self.version}")

    @log_function_calls()
    def register_service(self) -> bool:
        """
        Register the service with the rApp Catalogue.

        Returns:
            bool: True if registration was successful, False otherwise
            
        Raises:
            RAppRegistrationError: If registration fails due to client error
        """
        try:
            self.logger.info(f"Registering service '{self.service_name}' with rApp Catalogue")
            
            # Prepare request
            complete_url = f"{self.base_url}/{self.service_name}"
            headers = {"Content-Type": "application/json"}
            
            body = {
                "version": self.version,
                "display_name": self.display_name,
                "description": self.description,
            }
            
            self.logger.debug(f"Registration URL: {complete_url}")
            self.logger.debug(f"Registration payload: {body}")
            
            # Send registration request
            response = requests.put(
                complete_url, 
                json=body, 
                headers=headers, 
                verify=False,  # Note: In production, consider proper SSL verification
                timeout=30
            )
            
            # Handle response
            if response.ok:
                self.logger.info(f"Service '{self.service_name}' successfully registered")
                self.logger.debug(f"Registration response: {response.text}")
                return True
            else:
                self.logger.error(
                    f"Failed to register service '{self.service_name}' - "
                    f"Status: {response.status_code}, Response: {response.text}"
                )
                return False
                
        except requests.exceptions.Timeout:
            self.logger.error("Registration request timed out")
            return False
        except requests.exceptions.ConnectionError:
            self.logger.error(f"Failed to connect to rApp Catalogue at {self.base_url}")
            return False
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error during registration: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during service registration: {e}")
            raise RAppRegistrationError(f"Service registration failed: {e}")
    
    @log_function_calls()
    def unregister_service(self) -> bool:
        """
        Unregister the service from the rApp Catalogue.

        Returns:
            bool: True if unregistration was successful, False otherwise
        """
        try:
            self.logger.info(f"Unregistering service '{self.service_name}' from rApp Catalogue")
            
            complete_url = f"{self.base_url}/{self.service_name}"
            
            response = requests.delete(
                complete_url,
                verify=False,
                timeout=30
            )
            
            if response.ok:
                self.logger.info(f"Service '{self.service_name}' successfully unregistered")
                return True
            else:
                self.logger.error(
                    f"Failed to unregister service '{self.service_name}' - "
                    f"Status: {response.status_code}, Response: {response.text}"
                )
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error during service unregistration: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during service unregistration: {e}")
            return False
    
    @log_function_calls()
    def check_service_status(self) -> Optional[Dict[str, Any]]:
        """
        Check the registration status of the service.

        Returns:
            Optional[Dict[str, Any]]: Service information if registered, None otherwise
        """
        try:
            self.logger.debug(f"Checking status of service '{self.service_name}'")
            
            complete_url = f"{self.base_url}/{self.service_name}"
            
            response = requests.get(
                complete_url,
                verify=False,
                timeout=30
            )
            
            if response.ok:
                service_info = response.json()
                self.logger.info(f"Service '{self.service_name}' is registered")
                return service_info
            elif response.status_code == 404:
                self.logger.info(f"Service '{self.service_name}' is not registered")
                return None
            else:
                self.logger.warning(
                    f"Unexpected response when checking service status - "
                    f"Status: {response.status_code}, Response: {response.text}"
                )
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error checking service status: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error checking service status: {e}")
            return None


# Legacy class for backward compatibility
class rAppCatalalogueClient(RAppCatalogueClient):
    """
    DEPRECATED: Legacy class name with typo. Use RAppCatalogueClient instead.
    """
    
    def __init__(self, config_source):
        import warnings
        warnings.warn(
            "rAppCatalalogueClient is deprecated due to typo. Use RAppCatalogueClient instead.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(config_source)