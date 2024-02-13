
#!/bin/bash

# Define the namespaces if they are different from the default
# If they are all in the same namespace, you can set it here, otherwise you'll need to specify it for each component
NAMESPACE=nonrtric

# Restart deployments
DEPLOYMENTS=(
  "a1controller"
  "capifcore"
  "controlpanel"
  "db"
  "nonrtricgateway"
  "orufhrecovery"
  "ransliceassurance"
  "rappcatalogueenhancedservice"
  "rappcatalogueservice"
)

for DEPLOYMENT in "${DEPLOYMENTS[@]}"
do
  kubectl rollout restart deployment/$DEPLOYMENT -n $NAMESPACE
done

# Restart stateful sets
STATEFULSETS=(
  "a1-sim-osc"
  "a1-sim-std"
  "a1-sim-std2"
  "dmaapadapterservice"
  "dmaapmediatorservice"
  "helmmanager"
  "informationservice"
  "policymanagementservice"
)

for STATEFULSET in "${STATEFULSETS[@]}"
do
  kubectl rollout restart statefulset/$STATEFULSET -n $NAMESPACE
done

echo "Restart commands issued for all deployments and stateful sets."
