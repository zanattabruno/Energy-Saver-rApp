import requests
import yaml
import logging

logger = logging.getLogger(__name__)

class rAppCatalalogueClient:
    """
    A client for registering a service with the rApp Catalogue.

    Attributes:
        base_url (str): The base URL of the rApp Catalogue.
        service_name (str): The name of the service to register.
        version (str): The version of the service to register.
        display_name (str): The display name of the service to register.
        description (str): The description of the service to register.
    """

    def __init__(self, config_file_path):
        """
        Initializes a new instance of the rAppCatalalogueClient class.

        Args:
            config_file_path (str): The path to the YAML configuration file.
        """
        # Load configuration from the YAML file
        with open(config_file_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Initialize attributes based on configuration
        self.base_url = config['nonrtric']['base_url_rApp_catalogue']
        self.service_name = config['nonrtric']['service_name']
        self.version = config['nonrtric']['service_version']
        self.display_name = config['nonrtric']['service_display_name']
        self.description = config['nonrtric']['service_description']

    def register_service(self):
        """
        Sends a PUT request to a specified URL with a JSON payload containing the version, display name,
        and description of a service. If the response is not successful, it prints an error message and returns False.
        Otherwise, it returns True.

        Returns:
            bool: True if the request was successful, False otherwise.
        """
        complete_url = self.base_url + "/" + self.service_name
        headers = {"content-type": "application/json"}
        body = {
            "version": self.version,
            "display_name": self.display_name,
            "description": self.description,
        }
        resp = requests.put(complete_url, json=body, headers=headers, verify=False)
        if not resp.ok:
            logger.error("Failed to register service: %s", resp.text)
            return False
        else:
            logger.debug("Successfully registered service with body: %s", body)
            return True