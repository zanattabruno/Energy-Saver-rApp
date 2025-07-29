#!/bin/bash
echo "Scaling Apps to 0..." &&
kubectl scale deployment e2sim-e2sim-helm --replicas=0 -n ricplt &&
kubectl scale deployment ricxapp-bouncer-xapp --replicas=0 -n ricxapp &&
kubectl scale deployment ricxapp-debugger-xapp --replicas=0 -n ricxapp

echo "Waiting for all pods to terminate..."
sleep 10

echo "Scaling Apps back to 1..." &&
kubectl scale deployment e2sim-e2sim-helm --replicas=1 -n ricplt &&
kubectl scale deployment ricxapp-bouncer-xapp --replicas=1 -n ricxapp &&
kubectl scale deployment ricxapp-debugger-xapp --replicas=1 -n ricxapp

echo "All apps have been scaled down and back up. Apps restart complete." 