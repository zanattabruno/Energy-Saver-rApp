#!/bin/bash


curl -v -X PUT "http://nonrtricgateway.nonrtric.svc.cluster.local:9090/a1-policy/v2/policies" \
-H "Content-Type: application/json" \
-d @E2nodeEnergySaverExampleInstance.json
