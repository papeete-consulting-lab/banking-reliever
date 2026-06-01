#!/bin/sh
# BNK.RLVR.CAP.BSP.001.TIE — /health HTTP shim.
#
# Listens on $PORT with socat and forks the responder (`health-respond.sh`)
# for each accepted TCP connection. The responder writes the HTTP/1.0
# response to stdout — socat bridges to the socket and closes it.
#
# WORKER_PID is exported so the responder can decide 200 vs 503.

set -eu

PORT="${PORT:-20393}"
WORKER_PID="${WORKER_PID:-0}"

export WORKER_PID

exec socat -T2 \
    TCP-LISTEN:"$PORT",reuseaddr,fork,bind=0.0.0.0 \
    EXEC:/usr/local/bin/health-respond.sh
