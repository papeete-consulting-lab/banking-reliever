#!/bin/sh
# BNK.RLVR.CAP.BSP.001.TIE — stub container entrypoint.
#
# Launches the .NET worker AND the /health HTTP shim in parallel.
# tini (PID 1) reaps zombies and forwards SIGTERM to both children.

set -eu

PORT="${COMPONENT_PORT:-20393}"

# Start the .NET BackgroundService worker.
dotnet /app/Reliever.TierManagement.Stub.dll &
WORKER_PID=$!

# Start the health shim — reports 200 OK iff PID $WORKER_PID is alive.
WORKER_PID="$WORKER_PID" PORT="$PORT" /usr/local/bin/health-shim.sh &
SHIM_PID=$!

# Forward SIGTERM/SIGINT to both children, then wait.
trap 'kill -TERM "$WORKER_PID" "$SHIM_PID" 2>/dev/null || true' TERM INT

# Wait on the worker — its exit (success or failure) terminates the container.
wait "$WORKER_PID"
WORKER_RC=$?

# Stop the shim once the worker is gone.
kill -TERM "$SHIM_PID" 2>/dev/null || true
wait "$SHIM_PID" 2>/dev/null || true

exit "$WORKER_RC"
