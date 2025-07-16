import requests
import logging
from typing import Dict, List, Optional
from collections import defaultdict
import json
from prometheus_client.parser import text_string_to_metric_families
from urllib.parse import urljoin

class PrometheusClient:
    """
    Client for collecting and organizing Prometheus metrics using the official prometheus_client library.
    """
    
    def __init__(self, prometheus_url: str):
        """
        Initialize the Prometheus client.
        
        Args:
            prometheus_url (str): The base URL of the Prometheus server
        """
        self.prometheus_url = prometheus_url.rstrip('/')
        self.logger = logging.getLogger(__name__)
        
    def query_metric(self, query: str) -> Optional[Dict]:
        """
        Query Prometheus for a specific metric using the /api/v1/query endpoint.
        
        Args:
            query (str): The Prometheus query string
            
        Returns:
            Optional[Dict]: The query result or None if failed
        """
        try:
            url = f"{self.prometheus_url}/api/v1/query"
            params = {'query': query}
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') != 'success':
                self.logger.error(f"Prometheus query failed: {data.get('error', 'Unknown error')}")
                return None
                
            return data.get('data', {})
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error querying Prometheus: {e}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing Prometheus response: {e}")
            return None
    
    def get_metrics_from_endpoint(self, endpoint: str = '/metrics') -> Optional[List]:
        """
        Get metrics directly from Prometheus /metrics endpoint and parse using prometheus_client.
        
        Args:
            endpoint (str): The metrics endpoint path
            
        Returns:
            Optional[List]: List of metric families or None if failed
        """
        try:
            url = urljoin(self.prometheus_url, endpoint)
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse metrics using prometheus_client parser
            metric_families = list(text_string_to_metric_families(response.text))
            return metric_families
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching metrics from {url}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error parsing metrics: {e}")
            return None
    
    def collect_sinr_metrics(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Collect and organize SINR metrics from Prometheus using the official prometheus_client library.
        
        Returns:
            Dict: Organized metrics in the format:
            {
                "imsi": {
                    "gnbid": {
                        "pci": sinr_value
                    }
                }
            }
        """
        self.logger.info("Collecting SINR metrics from Prometheus")
        
        # First try to get metrics from the direct metrics endpoint
        metric_families = self.get_metrics_from_endpoint()
        organized_metrics = defaultdict(lambda: defaultdict(dict))
        
        if metric_families:
            # Parse using prometheus_client parser
            for family in metric_families:
                if family.name == 'e2sm_rc_report_style4_sinr':
                    for sample in family.samples:
                        labels = sample.labels
                        value = sample.value
                        
                        imsi = labels.get('imsi')
                        gnbid = labels.get('gnbid')
                        pci = labels.get('pci')
                        
                        if imsi and gnbid and pci is not None:
                            try:
                                organized_metrics[imsi][gnbid][pci] = float(value)
                            except (ValueError, TypeError):
                                self.logger.warning(f"Invalid SINR value for IMSI {imsi}, GNB {gnbid}, PCI {pci}")
        
        # If no metrics found from direct endpoint, try query API
        if not organized_metrics:
            self.logger.info("No metrics found from direct endpoint, trying query API")
            query = "e2sm_rc_report_style4_sinr"
            result = self.query_metric(query)
            
            if result:
                for metric_data in result.get('result', []):
                    metric_labels = metric_data.get('metric', {})
                    metric_value = metric_data.get('value', [None, None])
                    
                    imsi = metric_labels.get('imsi')
                    gnbid = metric_labels.get('gnbid')
                    pci = metric_labels.get('pci')
                    
                    if imsi and gnbid and pci is not None:
                        try:
                            sinr_value = float(metric_value[1])
                            organized_metrics[imsi][gnbid][pci] = sinr_value
                        except (ValueError, TypeError, IndexError):
                            self.logger.warning(f"Invalid SINR value for IMSI {imsi}, GNB {gnbid}, PCI {pci}")
        
        # Convert defaultdict to regular dict for cleaner output
        result_dict = {}
        for imsi, gnb_data in organized_metrics.items():
            result_dict[imsi] = {}
            for gnbid, pci_data in gnb_data.items():
                result_dict[imsi][gnbid] = dict(pci_data)
        
        self.logger.info(f"Collected SINR metrics for {len(result_dict)} IMSIs")
        return result_dict