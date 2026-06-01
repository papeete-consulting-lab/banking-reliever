#!/bin/sh
# BNK.RLVR.CAP.BSP.001.TIE — single-request /health responder.
#
# Invoked by socat (via health-shim.sh) once per accepted TCP connection.
# Reads the request from stdin (best-effort, ignored) and writes the HTTP
# response to stdout. Exits — socat closes the socket.
#
# Liveness contract:
#   - 200 OK if PID $WORKER_PID is alive
#   - 503    otherwise
# Routing is intentionally not enforced — the contract is liveness, not /health
# vs other paths (the upstream LB / k8s probe targets /health explicitly).

WORKER_PID="${WORKER_PID:-0}"

if kill -0 "$WORKER_PID" 2>/dev/null; then
    body="ok"
    status_line="HTTP/1.0 200 OK"
else
    body="worker-down"
    status_line="HTTP/1.0 503 Service Unavailable"
fi

len=$(printf "%s" "$body" | wc -c)

# CRLF line endings per HTTP/1.0.
printf "%s\r\n" "$status_line"
printf "Content-Type: text/plain\r\n"
printf "Content-Length: %s\r\n" "$len"
printf "Connection: close\r\n"
printf "\r\n"
printf "%s" "$body"
