#!/bin/bash
echo "Scaling Near-RT RIC to 0..." &&
kubectl scale deployment deployment-ricplt-e2term-r4-e2term-alpha --replicas=0 -n ricplt &
kubectl scale statefulset statefulset-ricplt-dbaas-server --replicas=0 -n ricplt &
kubectl scale deployment deployment-ricplt-a1mediator --replicas=0 -n ricplt &
kubectl scale deployment deployment-ricplt-alarmmanager --replicas=0 -n ricplt &
kubectl scale deployment deployment-ricplt-appmgr --replicas=0 -n ricplt &
kubectl scale deployment deployment-ricplt-e2mgr --replicas=0 -n ricplt &
kubectl scale deployment deployment-ricplt-o1mediator --replicas=0 -n ricplt &
kubectl scale deployment deployment-ricplt-rtmgr --replicas=0 -n ricplt &
kubectl scale deployment deployment-ricplt-submgr --replicas=0 -n ricplt &
kubectl scale deployment deployment-ricplt-vespamgr --replicas=0 -n ricplt & 
kubectl scale deployment r4-infrastructure-prometheus-server --replicas=0 -n ricplt &
kubectl scale deployment r4-infrastructure-prometheus-alertmanager --replicas=0 -n ricplt

echo "Scaling Non-RT RIC to 0..." &&
kubectl scale deployment a1controller --replicas=0 -n nonrtric &
kubectl scale deployment capifcore --replicas=0 -n nonrtric &
kubectl scale deployment controlpanel --replicas=0 -n nonrtric &
kubectl scale deployment db --replicas=0 -n nonrtric &
kubectl scale deployment nonrtricgateway --replicas=0 -n nonrtric &
kubectl scale deployment orufhrecovery --replicas=0 -n nonrtric &
kubectl scale deployment ransliceassurance --replicas=0 -n nonrtric &
kubectl scale deployment rappcatalogueenhancedservice --replicas=0 -n nonrtric &
kubectl scale deployment rappcatalogueservice --replicas=0 -n nonrtric &
kubectl scale statefulset a1-sim-osc --replicas=0 -n nonrtric &
kubectl scale statefulset a1-sim-std --replicas=0 -n nonrtric &
kubectl scale statefulset a1-sim-std2 --replicas=0 -n nonrtric &
kubectl scale statefulset dmaapadapterservice --replicas=0 -n nonrtric &
kubectl scale statefulset dmaapmediatorservice --replicas=0 -n nonrtric &
kubectl scale statefulset helmmanager --replicas=0 -n nonrtric &
kubectl scale statefulset informationservice --replicas=0 -n nonrtric &
kubectl scale statefulset policymanagementservice --replicas=0 -n nonrtric

echo "Scaling SMO to 0" &&
kubectl scale deployment chronograf-chronograf --replicas=0 -n smo &
kubectl scale deployment influxdb-connector --replicas=0 -n smo &
kubectl scale deployment kafdrop --replicas=0 -n smo &
kubectl scale deployment ves-collector --replicas=0 -n smo &
kubectl scale statefulset influxdb --replicas=0 -n smo &
kubectl scale statefulset kafka --replicas=0 -n smo &
kubectl scale statefulset kafka-zookeeper --replicas=0 -n smo

echo "Waiting for all pods to terminate..."
sleep 30

echo "Scaling Near-RT RIC back to 1..." &&
kubectl scale deployment deployment-ricplt-e2term-r4-e2term-alpha --replicas=1 -n ricplt &
kubectl scale statefulset statefulset-ricplt-dbaas-server --replicas=1 -n ricplt &
kubectl scale deployment deployment-ricplt-a1mediator --replicas=1 -n ricplt &
kubectl scale deployment deployment-ricplt-alarmmanager --replicas=1 -n ricplt &
kubectl scale deployment deployment-ricplt-appmgr --replicas=1 -n ricplt &
kubectl scale deployment deployment-ricplt-e2mgr --replicas=1 -n ricplt &
kubectl scale deployment deployment-ricplt-o1mediator --replicas=1 -n ricplt &
kubectl scale deployment deployment-ricplt-rtmgr --replicas=1 -n ricplt &
kubectl scale deployment deployment-ricplt-submgr --replicas=1 -n ricplt &
kubectl scale deployment deployment-ricplt-vespamgr --replicas=1 -n ricplt & 
kubectl scale deployment r4-infrastructure-prometheus-server --replicas=1 -n ricplt &
kubectl scale deployment r4-infrastructure-prometheus-alertmanager --replicas=1 -n ricplt

echo "Scaling Non-RT RIC back to 1..." &&
kubectl scale deployment a1controller --replicas=1 -n nonrtric &
kubectl scale deployment capifcore --replicas=1 -n nonrtric &
kubectl scale deployment controlpanel --replicas=1 -n nonrtric &
kubectl scale deployment db --replicas=1 -n nonrtric &
kubectl scale deployment nonrtricgateway --replicas=1 -n nonrtric &
kubectl scale deployment orufhrecovery --replicas=1 -n nonrtric &
kubectl scale deployment ransliceassurance --replicas=1 -n nonrtric &
kubectl scale deployment rappcatalogueenhancedservice --replicas=1 -n nonrtric &
kubectl scale deployment rappcatalogueservice --replicas=1 -n nonrtric &
kubectl scale statefulset a1-sim-osc --replicas=1 -n nonrtric &
kubectl scale statefulset a1-sim-std --replicas=1 -n nonrtric &
kubectl scale statefulset a1-sim-std2 --replicas=1 -n nonrtric &
kubectl scale statefulset dmaapadapterservice --replicas=1 -n nonrtric &
kubectl scale statefulset dmaapmediatorservice --replicas=1 -n nonrtric &
kubectl scale statefulset helmmanager --replicas=1 -n nonrtric &
kubectl scale statefulset informationservice --replicas=1 -n nonrtric &
kubectl scale statefulset policymanagementservice --replicas=1 -n nonrtric

echo "Scaling SMO back to 1" &&
kubectl scale deployment chronograf-chronograf --replicas=1 -n smo &
kubectl scale deployment influxdb-connector --replicas=1 -n smo &
kubectl scale deployment kafdrop --replicas=1 -n smo &
kubectl scale deployment ves-collector --replicas=1 -n smo &
kubectl scale statefulset influxdb --replicas=1 -n smo &
kubectl scale statefulset kafka --replicas=1 -n smo &
kubectl scale statefulset kafka-zookeeper --replicas=1 -n smo

echo "All services have been scaled down and back up. RIC restart complete."

