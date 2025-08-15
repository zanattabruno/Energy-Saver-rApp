#!/usr/bin/env bash

# Safe & robust restart script for key xApps/e2sim deployments.
# - Scales listed deployments to 0, waits for termination, then back to 1 and waits for rollout.
# - Options:
#     -t, --timeout <seconds>   Total wait per rollout/scale phase (default: 120)
#         --dry-run             Print actions without executing
#     -h, --help                Show help

set -Eeuo pipefail

SCRIPT_NAME=$(basename "$0")
TIMEOUT=120
DRY_RUN=0

usage() {
	cat <<EOF
Usage: $SCRIPT_NAME [options]

Restart known deployments by scaling down to 0 and back to 1 safely.

Options:
	-t, --timeout <seconds>   Timeout per phase (default: $TIMEOUT)
			--dry-run             Show what would be done without applying changes
	-h, --help                Show this help and exit
EOF
}

log()   { printf '%s\n' "[INFO]  $*"; }
warn()  { printf '%s\n' "[WARN]  $*" >&2; }
error() { printf '%s\n' "[ERROR] $*" >&2; }

trap 'error "An unexpected error occurred. Exiting."' ERR

# Parse CLI
while [[ $# -gt 0 ]]; do
	case "$1" in
		-t|--timeout)
			[[ $# -ge 2 ]] || { error "Missing value for $1"; exit 2; }
			TIMEOUT="$2"; shift 2 ;;
		--dry-run)
			DRY_RUN=1; shift ;;
		-h|--help)
			usage; exit 0 ;;
		*)
			error "Unknown option: $1"; usage; exit 2 ;;
	esac
done

# Required tool
if ! command -v kubectl >/dev/null 2>&1; then
	error "kubectl not found in PATH"
	exit 127
fi

# List of deployments to restart as namespace:deployment
DEPLOYMENTS=(
	"ricplt:e2sim-e2sim-helm"
	"ricxapp:ricxapp-bouncer-xapp"
	"ricxapp:ricxapp-debugger-xapp"
)

run_cmd() {
	if [[ "$DRY_RUN" -eq 1 ]]; then
		echo "DRY-RUN: $*"
	else
		eval "$@"
	fi
}

deployment_exists() {
	local ns="$1" dep="$2"
	kubectl -n "$ns" get deploy "$dep" >/dev/null 2>&1
}

scale_deployment() {
	local ns="$1" dep="$2" replicas="$3"
	if ! deployment_exists "$ns" "$dep"; then
		warn "Deployment $dep not found in namespace $ns. Skipping."
		return 0
	fi
	log "Scaling $ns/$dep to replicas=$replicas"
	run_cmd kubectl -n "$ns" scale deployment "$dep" --replicas="$replicas"
}

wait_for_scale_down() {
	local ns="$1" dep="$2" timeout="$3"
	# Poll until status.replicas and availableReplicas are 0 or empty
	local start ts
	start=$(date +%s)
	while true; do
		# If deployment was removed, treat as done
		if ! deployment_exists "$ns" "$dep"; then
			warn "Deployment $ns/$dep disappeared while waiting; treating as done."
			return 0
		fi
		local spec replicas avail
		spec=$(kubectl -n "$ns" get deploy "$dep" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo 0)
		replicas=$(kubectl -n "$ns" get deploy "$dep" -o jsonpath='{.status.replicas}' 2>/dev/null || echo 0)
		avail=$(kubectl -n "$ns" get deploy "$dep" -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo 0)
		[[ -z "$replicas" ]] && replicas=0
		[[ -z "$avail" ]] && avail=0
		if [[ "${spec:-0}" -eq 0 && "$replicas" -eq 0 && "$avail" -eq 0 ]]; then
			log "Scaled down confirmed: $ns/$dep"
			return 0
		fi
		ts=$(date +%s)
		if (( ts - start > timeout )); then
			error "Timeout waiting for $ns/$dep to scale down"
			return 1
		fi
		sleep 2
	done
}

wait_for_rollout() {
	local ns="$1" dep="$2" timeout="$3"
	if ! deployment_exists "$ns" "$dep"; then
		warn "Deployment $dep not found in namespace $ns during rollout wait. Skipping."
		return 0
	fi
	log "Waiting for rollout: $ns/$dep (timeout ${timeout}s)"
	if [[ "$DRY_RUN" -eq 1 ]]; then
		echo "DRY-RUN: kubectl -n $ns rollout status deploy/$dep --timeout=${timeout}s"
		return 0
	fi
	kubectl -n "$ns" rollout status deploy/"$dep" --timeout="${timeout}s"
}

# Scale all to 0 (in parallel) and wait
log "Scaling Apps to 0..."
declare -a pids_down=()
for entry in "${DEPLOYMENTS[@]}"; do
	IFS=":" read -r ns dep <<<"$entry"
	# Run scale in background to parallelize
	(
		scale_deployment "$ns" "$dep" 0
	) & pids_down+=("$!")
done

# Wait background scales
for pid in "${pids_down[@]}"; do
	wait "$pid"
done

# Confirm scale down
for entry in "${DEPLOYMENTS[@]}"; do
	IFS=":" read -r ns dep <<<"$entry"
	wait_for_scale_down "$ns" "$dep" "$TIMEOUT"
done

# Scale back to 1 (in parallel) and wait for rollout
log "Scaling Apps back to 1..."
declare -a pids_up=()
for entry in "${DEPLOYMENTS[@]}"; do
	IFS=":" read -r ns dep <<<"$entry"
	(
		scale_deployment "$ns" "$dep" 1
	) & pids_up+=("$!")
done

for pid in "${pids_up[@]}"; do
	wait "$pid"
done

for entry in "${DEPLOYMENTS[@]}"; do
	IFS=":" read -r ns dep <<<"$entry"
	wait_for_rollout "$ns" "$dep" "$TIMEOUT"
done

log "All apps have been scaled down and back up. Apps restart complete."