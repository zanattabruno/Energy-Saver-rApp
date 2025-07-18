#!/bin/bash
echo "Restarting Apps." &&
kubectl rollout restart deployment e2sim-e2sim-helm -n ricplt &&
sleep 5 &&
kubectl rollout restart deployment ricxapp-bouncer-xapp -n ricxapp &&
sleep 5 &&
kubectl rollout restart deployment ricxapp-debugger-xapp -n ricxapp &&
printf "Apps restarted successfully.\n" 