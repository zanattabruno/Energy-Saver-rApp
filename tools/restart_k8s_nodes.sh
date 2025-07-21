#!/bin/bash

# Simple script to restart all nodes: node3, node2, then node1 (current node)
# Usage: ./restart_k8s_nodes.sh

echo "Starting node restart sequence..."

# Reboot node3
echo "Rebooting node3..."
ssh vmladmin@node3 "sudo reboot || sudo /sbin/reboot || sudo systemctl reboot" &

# Wait for SSH commands to be sent
echo "Waiting 30 seconds for remote reboots to start..."
sleep 15

# Reboot node2  
echo "Rebooting node2..."
ssh vmladmin@node2 "sudo reboot || sudo /sbin/reboot || sudo systemctl reboot" &

# Wait for SSH commands to be sent
echo "Waiting 15 seconds for remote reboots to start..."
sleep 15

# Reboot current node (node1)
echo "Rebooting node1 (current node)..."
sudo reboot
