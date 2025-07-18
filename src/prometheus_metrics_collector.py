"""
Prometheus Metrics Collector for Energy Saver rApp.

This module provides functionality to collect and organize SINR metrics 
and MCC/MNC data from Prometheus using both direct metrics endpoint 
and query API approaches.
"""

import json
import logging
import requests
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from urllib.parse import urljoin

try:
    from prometheus_client.parser import text_string_to_metric_families
except ImportError:
    text_string_to_metric_families = None

from utils.logging_manager import LoggingManager, log_function_calls
from utils.exceptions import PrometheusConnectionError, PrometheusQueryError, MetricsCollectionError


class PrometheusClient:
    """
    Advanced client for collecting and organizing Prometheus metrics.
    
    This client supports both direct metrics endpoint access and query API,
    providing optimized collection of SINR metrics and MCC/MNC data.
    """
    
    def __init__(self, prometheus_url: str, timeout: int = 30):
        """
        Initialize the Prometheus client.
        
        Args:
            prometheus_url (str): The base URL of the Prometheus server
            timeout (int): Request timeout in seconds
            
        Raises:
            PrometheusConnectionError: If unable to connect to Prometheus
        """
        self.prometheus_url = prometheus_url.rstrip('/')
        self.timeout = timeout
        self.logger = LoggingManager.get_logger(__name__)
        
        # Validate Prometheus connection
        self._validate_connection()
        
        self.logger.info(f"Prometheus client initialized for URL: {self.prometheus_url}")
    
    def _validate_connection(self) -> None:
        """
        Validate connection to Prometheus server.
        
        Raises:
            PrometheusConnectionError: If unable to connect
        """
        try:
            response = requests.get(
                f"{self.prometheus_url}/-/healthy",
                timeout=self.timeout
            )
            if not response.ok:
                raise PrometheusConnectionError(
                    f"Prometheus server unhealthy: {response.status_code}"
                )
        except requests.exceptions.RequestException as e:
            raise PrometheusConnectionError(f"Cannot connect to Prometheus: {e}")
    
    @log_function_calls()
    def query_metric(self, query: str) -> Optional[Dict]:
        """
        Query Prometheus for a specific metric using the /api/v1/query endpoint.
        
        Args:
            query (str): The Prometheus query string
            
        Returns:
            Optional[Dict]: The query result or None if failed
            
        Raises:
            PrometheusQueryError: If query execution fails
        """
        try:
            url = f"{self.prometheus_url}/api/v1/query"
            params = {'query': query}
            
            self.logger.debug(f"Executing Prometheus query: {query}")
            
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') != 'success':
                error_msg = data.get('error', 'Unknown error')
                self.logger.error(f"Prometheus query failed: {error_msg}")
                raise PrometheusQueryError(f"Query failed: {error_msg}")
                
            result = data.get('data', {})
            result_count = len(result.get('result', []))
            self.logger.debug(f"Query returned {result_count} results")
            
            return result
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error querying Prometheus: {e}")
            raise PrometheusQueryError(f"Query request failed: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing Prometheus response: {e}")
            raise PrometheusQueryError(f"Invalid JSON response: {e}")
    
    @log_function_calls()
    def get_metrics_from_endpoint(self, endpoint: str = '/metrics') -> Optional[List]:
        """
        Get metrics directly from Prometheus /metrics endpoint and parse using prometheus_client.
        
        Args:
            endpoint (str): The metrics endpoint path
            
        Returns:
            Optional[List]: List of metric families or None if failed
            
        Raises:
            MetricsCollectionError: If metrics collection fails
        """
        if text_string_to_metric_families is None:
            self.logger.warning("prometheus_client not available, falling back to query API")
            return None
        
        try:
            url = urljoin(self.prometheus_url, endpoint)
            self.logger.debug(f"Fetching metrics from endpoint: {url}")
            
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse metrics using prometheus_client parser
            metric_families = list(text_string_to_metric_families(response.text))
            
            self.logger.debug(f"Parsed {len(metric_families)} metric families")
            return metric_families
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching metrics from {url}: {e}")
            raise MetricsCollectionError(f"Failed to fetch metrics: {e}")
        except Exception as e:
            self.logger.error(f"Error parsing metrics: {e}")
            raise MetricsCollectionError(f"Failed to parse metrics: {e}")
    
    @log_function_calls()
    def collect_sinr_metrics(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Collect and organize SINR metrics from Prometheus.
        
        DEPRECATED: Use collect_sinr_metrics_and_mcc_mnc() for better performance.
        
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
        import warnings
        warnings.warn(
            "collect_sinr_metrics is deprecated. Use collect_sinr_metrics_and_mcc_mnc() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Use the optimized method and return only the metrics part
        metrics, _ = self.collect_sinr_metrics_and_mcc_mnc()
        return metrics
    
    @log_function_calls()
    def collect_sinr_metrics_and_mcc_mnc(self) -> Tuple[Dict[str, Dict[str, Dict[str, float]]], Optional[Dict[str, str]]]:
        """
        Collect and organize SINR metrics AND extract MCC/MNC from Prometheus in a single optimized call.
        
        This method tries the direct metrics endpoint first for better performance,
        then falls back to the query API if needed.
        
        Returns:
            Tuple containing:
            - organized_metrics: Dict in the format {imsi: {gnbid: {pci: sinr_value}}}
            - mcc_mnc_data: Dict with 'mcc' and 'mnc' keys, or None if not found
            
        Raises:
            MetricsCollectionError: If both collection methods fail
        """
        self.logger.info("Starting optimized SINR metrics and MCC/MNC collection")
        
        organized_metrics = defaultdict(lambda: defaultdict(dict))
        mcc_mnc_data = {}  # Use dict instead of None so it can be modified by reference
        
        # Method 1: Try direct metrics endpoint first (more efficient)
        success = self._collect_from_metrics_endpoint(organized_metrics, mcc_mnc_data)
        
        # Method 2: Fall back to query API if direct endpoint failed
        if not success:
            self.logger.info("Direct endpoint collection failed, trying query API")
            success = self._collect_from_query_api(organized_metrics, mcc_mnc_data)
        
        if not success:
            raise MetricsCollectionError("Failed to collect metrics using both direct endpoint and query API")
        
        # Convert defaultdict to regular dict for cleaner output
        result_dict = self._convert_to_regular_dict(organized_metrics)
        
        # Return None if no MCC/MNC data was found
        final_mcc_mnc_data = mcc_mnc_data if mcc_mnc_data.get('mcc') and mcc_mnc_data.get('mnc') else None
        
        # Log collection summary
        self._log_collection_summary(result_dict, final_mcc_mnc_data)
        
        return result_dict, final_mcc_mnc_data
    
    def _collect_from_metrics_endpoint(
        self, 
        organized_metrics: defaultdict, 
        mcc_mnc_data: Dict[str, str]
    ) -> bool:
        """
        Collect metrics from the direct metrics endpoint.
        
        Args:
            organized_metrics: Dictionary to populate with metrics
            mcc_mnc_data: Dictionary to populate with MCC/MNC data
            
        Returns:
            bool: True if collection was successful, False otherwise
        """
        try:
            metric_families = self.get_metrics_from_endpoint()
            if not metric_families:
                return False
            
            # Parse using prometheus_client parser
            found_metrics = False
            for family in metric_families:
                if family.name == 'e2sm_rc_report_style4_sinr':
                    found_metrics = True
                    for sample in family.samples:
                        self._process_sample(sample, organized_metrics, mcc_mnc_data)
            
            return found_metrics
            
        except Exception as e:
            self.logger.warning(f"Direct endpoint collection failed: {e}")
            return False
    
    def _collect_from_query_api(
        self, 
        organized_metrics: defaultdict, 
        mcc_mnc_data: Dict[str, str]
    ) -> bool:
        """
        Collect metrics from the Prometheus query API.
        
        Args:
            organized_metrics: Dictionary to populate with metrics
            mcc_mnc_data: Dictionary to populate with MCC/MNC data
            
        Returns:
            bool: True if collection was successful, False otherwise
        """
        try:
            query = "e2sm_rc_report_style4_sinr"
            result = self.query_metric(query)
            
            if not result:
                return False
            
            found_metrics = False
            for metric_data in result.get('result', []):
                found_metrics = True
                self._process_query_result(metric_data, organized_metrics, mcc_mnc_data)
            
            return found_metrics
            
        except Exception as e:
            self.logger.error(f"Query API collection failed: {e}")
            return False
    
    def _process_sample(
        self, 
        sample, 
        organized_metrics: defaultdict, 
        mcc_mnc_data: Dict[str, str]
    ) -> None:
        """
        Process a single metric sample from the direct endpoint.
        
        Args:
            sample: Prometheus sample object
            organized_metrics: Dictionary to populate with metrics
            mcc_mnc_data: Dictionary to populate with MCC/MNC data
        """
        labels = sample.labels
        value = sample.value
        
        imsi = labels.get('imsi')
        gnbid = labels.get('gnbid')
        pci = labels.get('pci')
        mcc = labels.get('mcc')
        mnc = labels.get('mnc')
        
        # Extract MCC/MNC if found and not yet collected
        if mcc and mnc and not mcc_mnc_data.get('mcc'):
            mcc_mnc_data['mcc'] = str(mcc)
            mcc_mnc_data['mnc'] = str(mnc)
            self.logger.info(f"Found MCC: {mcc}, MNC: {mnc} from Prometheus metrics")
        
        # Extract SINR metrics
        if imsi and gnbid and pci is not None:
            try:
                organized_metrics[imsi][gnbid][pci] = float(value)
            except (ValueError, TypeError):
                self.logger.warning(f"Invalid SINR value for IMSI {imsi}, GNB {gnbid}, PCI {pci}")
    
    def _process_query_result(
        self, 
        metric_data: Dict, 
        organized_metrics: defaultdict, 
        mcc_mnc_data: Dict[str, str]
    ) -> None:
        """
        Process a single metric result from the query API.
        
        Args:
            metric_data: Query result data
            organized_metrics: Dictionary to populate with metrics
            mcc_mnc_data: Dictionary to populate with MCC/MNC data
        """
        metric_labels = metric_data.get('metric', {})
        metric_value = metric_data.get('value', [None, None])
        
        imsi = metric_labels.get('imsi')
        gnbid = metric_labels.get('gnbid')
        pci = metric_labels.get('pci')
        mcc = metric_labels.get('mcc')
        mnc = metric_labels.get('mnc')
        
        # Extract MCC/MNC if found and not yet collected
        if mcc and mnc and not mcc_mnc_data.get('mcc'):
            mcc_mnc_data['mcc'] = str(mcc)
            mcc_mnc_data['mnc'] = str(mnc)
            self.logger.info(f"Found MCC: {mcc}, MNC: {mnc} from Prometheus query API")
        
        # Extract SINR metrics
        if imsi and gnbid and pci is not None:
            try:
                sinr_value = float(metric_value[1])
                organized_metrics[imsi][gnbid][pci] = sinr_value
            except (ValueError, TypeError, IndexError):
                self.logger.warning(f"Invalid SINR value for IMSI {imsi}, GNB {gnbid}, PCI {pci}")
    
    def _convert_to_regular_dict(self, organized_metrics: defaultdict) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Convert defaultdict to regular dict for cleaner output.
        
        Args:
            organized_metrics: defaultdict structure
            
        Returns:
            Dict: Regular dictionary structure
        """
        result_dict = {}
        for imsi, gnb_data in organized_metrics.items():
            result_dict[imsi] = {}
            for gnbid, pci_data in gnb_data.items():
                result_dict[imsi][gnbid] = dict(pci_data)
        return result_dict
    
    def _log_collection_summary(
        self, 
        metrics: Dict[str, Dict[str, Dict[str, float]]], 
        mcc_mnc_data: Optional[Dict[str, str]]
    ) -> None:
        """
        Log a summary of the collection results.
        
        Args:
            metrics: Collected metrics
            mcc_mnc_data: Collected MCC/MNC data
        """
        imsi_count = len(metrics)
        total_measurements = sum(
            len(pci_data) 
            for gnb_data in metrics.values() 
            for pci_data in gnb_data.values()
        )
        
        self.logger.info(f"Metrics collection completed:")
        self.logger.info(f"  - IMSIs: {imsi_count}")
        self.logger.info(f"  - Total measurements: {total_measurements}")
        self.logger.info(f"  - MCC/MNC data: {'found' if mcc_mnc_data else 'not found'}")
        
        if not mcc_mnc_data:
            self.logger.warning("Could not extract MCC and MNC from Prometheus metrics")
    
    @log_function_calls()
    def get_available_metrics(self) -> List[str]:
        """
        Get a list of available metric names from Prometheus.
        
        Returns:
            List[str]: List of available metric names
        """
        try:
            query = "up"  # Simple query to test connectivity
            result = self.query_metric(query)
            
            if result:
                self.logger.info("Prometheus connectivity verified")
                
            # Get metric names from label API
            url = f"{self.prometheus_url}/api/v1/label/__name__/values"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            if data.get('status') == 'success':
                metrics = data.get('data', [])
                self.logger.info(f"Found {len(metrics)} available metrics")
                return metrics
            else:
                self.logger.error("Failed to retrieve metric names")
                return []
                
        except Exception as e:
            self.logger.error(f"Error retrieving available metrics: {e}")
            return []