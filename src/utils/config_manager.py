"""
Configuration management utilities for the Energy Saver rApp.

This module provides centralized configuration loading and validation.
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigManager:
    """
    Centralized configuration manager for the Energy Saver rApp.
    """
    
    def __init__(self, config_path: str):
        """
        Initialize the configuration manager.
        
        Args:
            config_path (str): Path to the configuration file
            
        Raises:
            FileNotFoundError: If configuration file doesn't exist
            yaml.YAMLError: If configuration file is invalid YAML
        """
        self.config_path = Path(config_path)
        self.logger = logging.getLogger(__name__)
        self._config: Optional[Dict[str, Any]] = None
        
        self._load_config()
        self._validate_config()
    
    def _load_config(self) -> None:
        """
        Load configuration from YAML file.
        
        Raises:
            FileNotFoundError: If configuration file doesn't exist
            yaml.YAMLError: If configuration file is invalid YAML
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self._config = yaml.safe_load(file)
            self.logger.info(f"Configuration loaded successfully from {self.config_path}")
        except yaml.YAMLError as e:
            self.logger.error(f"Invalid YAML in configuration file: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            raise
    
    def _validate_config(self) -> None:
        """
        Validate required configuration sections and keys.
        
        Raises:
            ValueError: If required configuration is missing
        """
        required_sections = ['nearrtric', 'nonrtric', 'policy']
        required_keys = {
            'nearrtric': ['prometheus_url'],
            'nonrtric': ['base_url_pms', 'base_url_rApp_catalogue'],
            'policy': ['ric_id', 'service_id', 'policy_type_id']
        }
        
        if not self._config:
            raise ValueError("Configuration is empty")
        
        for section in required_sections:
            if section not in self._config:
                raise ValueError(f"Missing required configuration section: {section}")
            
            for key in required_keys.get(section, []):
                if key not in self._config[section]:
                    raise ValueError(f"Missing required configuration key: {section}.{key}")
        
        self.logger.info("Configuration validation completed successfully")
    
    @property
    def config(self) -> Dict[str, Any]:
        """
        Get the loaded configuration.
        
        Returns:
            Dict[str, Any]: The configuration dictionary
        """
        return self._config or {}
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key_path (str): Dot-separated path to the configuration key (e.g., 'nearrtric.prometheus_url')
            default: Default value if key is not found
            
        Returns:
            Any: The configuration value or default
            
        Example:
            >>> config_manager.get('nearrtric.prometheus_url')
            'http://prometheus.server.com'
        """
        keys = key_path.split('.')
        value = self._config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            self.logger.warning(f"Configuration key not found: {key_path}, using default: {default}")
            return default
    
    def get_logging_config(self) -> Dict[str, Any]:
        """
        Get logging configuration with defaults.
        
        Returns:
            Dict[str, Any]: Logging configuration
        """
        return {
            'level': self.get('logging.level', 'INFO'),
            'format': self.get('logging.format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        }
    
    def get_prometheus_config(self) -> Dict[str, str]:
        """
        Get Prometheus configuration.
        
        Returns:
            Dict[str, str]: Prometheus configuration
        """
        return {
            'url': self.get('nearrtric.prometheus_url')
        }
    
    def get_policy_config(self) -> Dict[str, str]:
        """
        Get policy configuration.
        
        Returns:
            Dict[str, str]: Policy configuration
        """
        return {
            'ric_id': self.get('policy.ric_id'),
            'service_id': self.get('policy.service_id'),
            'policy_type_id': self.get('policy.policy_type_id')
        }
    
    def get_nonrtric_config(self) -> Dict[str, str]:
        """
        Get Non-RT RIC configuration.
        
        Returns:
            Dict[str, str]: Non-RT RIC configuration
        """
        return {
            'base_url_pms': self.get('nonrtric.base_url_pms'),
            'base_url_rapp_catalogue': self.get('nonrtric.base_url_rApp_catalogue'),
            'service_name': self.get('nonrtric.service_name'),
            'service_version': self.get('nonrtric.service_version'),
            'service_display_name': self.get('nonrtric.service_display_name'),
            'service_description': self.get('nonrtric.service_description')
        }
    
    def get_scheduler_config(self) -> Dict[str, Any]:
        """
        Get scheduler configuration.
        
        Returns:
            Dict[str, Any]: Scheduler configuration
        """
        return {
            'interval_minutes': self.get('scheduler.interval_minutes', 15),
            'run_on_startup': self.get('scheduler.run_on_startup', True)
        }
    
    def get_optimization_config(self) -> Dict[str, Any]:
        """
        Get optimization configuration.
        
        Returns:
            Dict[str, Any]: Optimization configuration
        """
        return {
            'method': self.get('optimization.method', 'optimal')
        }
