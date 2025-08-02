"""
Shared configuration and utilities for optimization wrappers.

This module provides common configuration values and helper functions
used by both optimal and heuristic optimization wrappers.
"""

from typing import Dict, Any, Tuple, List
import random


class OptimizationConfig:
    """Configuration constants for optimization models."""
    
    # E2 Node configuration
    E2NS_BW = 100
    E2NS_TX = 20
    E2NS_RF = 12.9
    E2NS_AMP = 0.388
    
    # Random seed for reproducibility
    RANDOM_SEED = 10
    
    # User demand profiles
    DEMANDS_PROFILE = [32, 25, 6, 3, 15, 12, 3, 1.5]
    
    # Default values
    DEFAULT_POOR_SIGNAL = -10
    TOTAL_BW_MULTIPLIER = 25


class OptimizationHelpers:
    """Helper functions for optimization data processing."""
    
    @staticmethod
    def extract_unique_nodes(input_json: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[int, Tuple[str, int]]]:
        """Extract unique E2 nodes from input data."""
        E2Ns = {"E2_nodes": []}
        ID_to_nodebid_and_PCI = {}
        seen_nodes = set()
        node_id = 0
        
        for user in input_json["users"]:
            node_key = (user["nodebid"], user["pci"])
            if node_key not in seen_nodes:
                seen_nodes.add(node_key)
                ID_to_nodebid_and_PCI[node_id] = node_key
                E2Ns["E2_nodes"].append({
                    "ID": node_id,
                    "nodebid": user["nodebid"],
                    "PCI": user["pci"],
                    "bandwidth": OptimizationConfig.E2NS_BW,
                    "max_power": OptimizationConfig.E2NS_TX,
                    "RF_consumption": OptimizationConfig.E2NS_RF,
                    "Power_amp_efficiency": OptimizationConfig.E2NS_AMP
                })
                node_id += 1
        
        return E2Ns, ID_to_nodebid_and_PCI
    
    @staticmethod
    def build_channel_gains(user_imsi: str, input_json: Dict[str, Any], 
                           ID_to_nodebid_and_PCI: Dict[int, Tuple[str, int]]) -> Dict[int, float]:
        """Build channel gain mapping for a user."""
        channel_gains = {}
        
        # Create lookup for faster access
        user_measurements = {}
        for u in input_json["users"]:
            if u["IMSI"] == user_imsi:
                key = (u["nodebid"], u["pci"])
                user_measurements[key] = u["sinr"]
        
        for e2n_id, (nodebid, pci) in ID_to_nodebid_and_PCI.items():
            channel_gains[e2n_id] = user_measurements.get(
                (nodebid, pci), 
                OptimizationConfig.DEFAULT_POOR_SIGNAL
            )
        
        return channel_gains
    
    @staticmethod
    def create_users_dict(input_json: Dict[str, Any], 
                         ID_to_nodebid_and_PCI: Dict[int, Tuple[str, int]]) -> Tuple[Dict[str, Any], Dict[int, str]]:
        """Create users dictionary for optimization."""
        UEs = {"users": []}
        ID_to_IMSI = {}
        seen_imsi = set()
        user_id = 0
        
        for user in input_json["users"]:
            if user["IMSI"] not in seen_imsi:
                seen_imsi.add(user["IMSI"])
                ID_to_IMSI[user_id] = user["IMSI"]
                
                channel_gains = OptimizationHelpers.build_channel_gains(
                    user["IMSI"], input_json, ID_to_nodebid_and_PCI
                )
                demand = random.choice(OptimizationConfig.DEMANDS_PROFILE)
                
                UEs["users"].append({
                    "ID": user_id,
                    "channel_gain": channel_gains,
                    "demand": demand
                })
                user_id += 1
        
        return UEs, ID_to_IMSI
    
    @staticmethod
    def build_gnb_configurations(ID_to_nodebid_and_PCI: Dict[int, Tuple[str, int]], 
                                E2N_info: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build GNB configurations from optimization results."""
        gnb_configs = {}
        
        # Initialize all GNBs
        for e2n_id, (gnb_id, pci) in ID_to_nodebid_and_PCI.items():
            if gnb_id not in gnb_configs:
                gnb_configs[gnb_id] = {
                    "gnb": gnb_id,
                    "status": "powered_off",
                    "all_pcis": []
                }
            
            # Add PCI configuration
            if e2n_id in E2N_info:
                pci_config = {
                    "pci": pci,
                    "bandwidth (MHz)": E2N_info[e2n_id]["bandwidth"],
                    "radioPower (dBm)": E2N_info[e2n_id]["power"],
                    "status": "active"
                }
            else:
                pci_config = {
                    "pci": pci,
                    "bandwidth (MHz)": None,
                    "radioPower (dBm)": None,
                    "status": "powered_off"
                }
            
            gnb_configs[gnb_id]["all_pcis"].append(pci_config)
        
        # Update GNB status based on active PCIs
        for config in gnb_configs.values():
            active_count = sum(1 for pci in config["all_pcis"] if pci["status"] == "active")
            total_count = len(config["all_pcis"])
            
            if active_count == 0:
                config["status"] = "powered_off"
            elif active_count == total_count:
                config["status"] = "active"
            else:
                config["status"] = "partial"
        
        return list(gnb_configs.values())
    
    @staticmethod
    def build_user_admissions(connections: Dict[int, int], 
                             ID_to_IMSI: Dict[int, str],
                             ID_to_nodebid_and_PCI: Dict[int, Tuple[str, int]]) -> List[Dict[str, Any]]:
        """Build user admissions list from optimization results."""
        user_admissions = []
        
        for user_id, e2n_id in connections.items():
            if user_id in ID_to_IMSI and e2n_id in ID_to_nodebid_and_PCI:
                gnb_id, pci = ID_to_nodebid_and_PCI[e2n_id]
                user_admissions.append({
                    "IMSI": ID_to_IMSI[user_id],
                    "gnb": gnb_id,
                    "pci": pci
                })
        
        return user_admissions


class OptimizationWrapper:
    """Base class for optimization wrappers."""
    
    def __init__(self):
        """Initialize the optimization wrapper."""
        self.config = OptimizationConfig()
        self.helpers = OptimizationHelpers()
        random.seed(self.config.RANDOM_SEED)
    
    def format_results(self, connections: Dict[int, int], E2N_info: Dict[int, Dict[str, Any]], 
                      ID_to_IMSI: Dict[int, str], ID_to_nodebid_and_PCI: Dict[int, Tuple[str, int]]) -> Dict[str, Any]:
        """Format optimization results to expected output format."""
        user_admissions = self.helpers.build_user_admissions(
            connections, ID_to_IMSI, ID_to_nodebid_and_PCI
        )
        gnb_configs = self.helpers.build_gnb_configurations(
            ID_to_nodebid_and_PCI, E2N_info
        )
        
        return {
            "Users admission": user_admissions,
            "GNB_config": gnb_configs
        }
