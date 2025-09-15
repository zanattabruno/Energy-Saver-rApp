# Energy Saver rApp

Reduce RAN energy consumption by collecting SINR metrics from Prometheus, running an energy-efficiency optimization (heuristic or optimal), and applying the result through O1 (gNB power configuration) and A1 (policy) to a Near-RT RIC.


## Key features
- Prometheus collector for e2sm_rc_report_style4_sinr with MCC/MNC extraction
- Optimizers:
  - Heuristic (fast) and Optimal (exact model)
- Deployment flow (power first, then policy):
  1) Configure gNB antenna gains via O1 (enable/disable PCIs, gain == power dBm)
  2) Create/PUT A1 policy instance to PMS
- Optional fixed-interval scheduling
- rApp Catalogue registration on startup
- Structured logging with call tracing


## Repository layout
- `src/rApp_Energy_Saver.py` — Main entrypoint (class `EnergySaverApplication`)
- `src/config/config.yaml` — App configuration (Prometheus, A1 PMS, O1, scheduler, optimization)
- `src/prometheus_metrics_collector.py` — Prometheus client and optimized SINR+MCC/MNC collection
- `src/policy_manager.py` — A1 policy lifecycle and O1-powered deployment
- `src/o1_interface_client.py` — O1 REST client to manage antenna gains (tx-gain)
- `src/rApp_catalogue_client.py` — rApp catalogue registration
- `src/utils/*` — logging, config, scheduler, exceptions
- `src/energy-efficiency-optimizer/*` — heuristic and optimal models + wrappers
- `helm/energy-saver-rapp` — Helm chart for Kubernetes deployment
- `tests/` — sample payloads and fixtures


## Requirements
- Python 3.8+
- Access to:
  - Prometheus exposing `e2sm_rc_report_style4_sinr` with labels `imsi, gnbid, pci, mcc, mnc`
  - A1 Policy Management Service (PMS v2)
  - O1 E2 simulator REST endpoint (tx-gain API)

Install Python deps:

```bash
pip install -r requirements.txt
```


## Configuration
Default config lives at `src/config/config.yaml`. Key sections:

- logging: level
- optimization.method: `heuristic` | `optimal`
- scheduler.interval_minutes: integer minutes (0 = single run)
- nonrtric:
  - base_url_pms: "http://.../a1-policy/v2"
  - base_url_rApp_catalogue: "http://.../services"
  - service_name/service_version/display_name/description
  - ric_id, policytype_id
- policy:
  - ric_id, service_id, policy_type_id
- nearrtric.prometheus_url: Prometheus base URL
- o1_interface.base_url: O1 base URL (default :8090), timeout

Example (trimmed):

```yaml
optimization:
  method: 'heuristic'

scheduler:
  interval_minutes: 0
  run_on_startup: true

nonrtric:
  base_url_rApp_catalogue: 'http://rappcatalogueservice.nonrtric.svc.cluster.local:9085/services'
  base_url_pms: 'http://nonrtricgateway.nonrtric.svc.cluster.local:9090/a1-policy/v2'
  ric_id: 'ric4'
  policytype_id: '5'

policy:
  ric_id: 'ric4'
  service_id: 'EnergySaverApp'
  policy_type_id: '5'

nearrtric:
  prometheus_url: 'http://r4-infrastructure-prometheus-server.ricplt.svc.cluster.local'

o1_interface:
  base_url: 'http://e2sim-e2sim-helm-o1.ricplt.svc.cluster.local:8090'
  timeout: 30
```


## How it works
1) Collect SINR and MCC/MNC from Prometheus:
   - Tries direct `/metrics` parsing first, falls back to `/api/v1/query` for `e2sm_rc_report_style4_sinr`
   - Output shape: `{ imsi: { gnbid: { pci: sinr_float } } }` plus `{mcc,mnc}`
2) Transform to optimizer input, including all PCIs discovered via O1 when available; missing SINR are estimated with penalties
3) Run optimization via wrappers:
   - Heuristic: `energy-efficiency-optimizer/heuristic_model/run_heuristic_wrapper.py::run_heuristic_optimization`
   - Optimal: `energy-efficiency-optimizer/optimal_model/run_optimization_wrapper.py::run_optimization`
   - Both return: `{ "Users admission": [...], "GNB_config": [...] }`
4) Deploy result with `PolicyManager.deploy_optimization_with_o1()`:
   - O1: apply full gNB power configuration first (enable active PCIs, disable others). Gain equals power(dBm). 0 disables.
   - A1: create policy instance and PUT to PMS


## Run locally
Run once with default config:

```bash
python src/rApp_Energy_Saver.py -c src/config/config.yaml --log-level INFO
```

Enable scheduled runs (set `scheduler.interval_minutes > 0` in config).


## Docker
Build image and run the app:

```bash
./build_container_image.sh
# image tag: rapp_energy-saver:TNSM-25 (see script)
```

The container entrypoint is bash; in deployments the app is launched as:

```bash
python3 src/rApp_Energy_Saver.py -c config/config.yaml
```


## Helm chart
Values map to the config via ConfigMap. Install in a cluster where Non-RT RIC, Near-RT RIC (PMS), Prometheus, and O1 simulator are reachable.

Chart: `helm/energy-saver-rapp`

Key values to review in `values.yaml`:
- image repository and tag
- config map content (Prometheus URL, PMS endpoints, O1 base URL)


## Data shapes and conventions
- Prometheus metrics: `{imsi: {gnbid: {pci: sinr}}}` (keys as strings)
- Optimizer input: `{ "users": [ {IMSI, nodebid, pci, sinr, ...} ] }`
- Optimizer output: 
  - `Users admission`: list of `{IMSI, gnb, pci}`
  - `GNB_config`: per-gNB entries with `all_pcis: [{pci, "radioPower (dBm)", status}]`
- O1 gains: `gain == power(dBm)`; disabling uses `gain=0.0`


## Tests and quick checks
- Sample JSONs are under `tests/` to sanity-check parsing and formatting.
- The optimal model has `src/energy-efficiency-optimizer/optimal_model/run_tests.py` for ad hoc checks.


## Troubleshooting
- Prometheus health: ensure `/-/healthy` responds. Verify metric `e2sm_rc_report_style4_sinr` exists.
- A1 PMS: `nonrtric.base_url_pms` must be reachable and accept `PUT /policies`.
- O1: `GET/POST` to `<o1_base>/restconf/operations/tx-gain` should work; 204 on set gain.
- Missing SINR for some PCIs: the app estimates with a penalty and logs counts.
- Increase log verbosity with `--log-level DEBUG`.


## License
See [LICENSE](LICENSE).
