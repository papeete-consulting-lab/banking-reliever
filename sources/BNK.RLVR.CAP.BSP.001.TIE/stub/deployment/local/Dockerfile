# BNK.RLVR.CAP.BSP.001.TIE — Tier Management — Mode-B Contract Stub
#
# Universal build artefact per the Deployment contract (CLAUDE.md
# § "Deployment contract (local + dev)"). Same image runs in local
# (docker compose) and dev (k8s, pulled from ECR by CI).
#
# Build context is the component root: `sources/BNK.RLVR.CAP.BSP.001.TIE/stub/`.
# Invoked from `deployment/local/docker-compose.yml` via:
#   build:
#     context: ../..
#     dockerfile: deployment/local/Dockerfile
#
# Health endpoint contract (CLAUDE.md):
#   GET /health → 200 on the component port (kind=api → 20393 for this capability).
#
# The application is a pure BackgroundService (no HTTP host in src/) and the
# task explicitly forbids touching `src/`. To satisfy the DoD `GET /health → 200`
# requirement entirely within `deployment/`, the container runs the .NET worker
# AND a tiny `socat`-based HTTP responder in parallel under tini. The responder
# replies 200 OK iff the worker process is alive (PID-based liveness).

# ----------------------------------------------------------------------
# Build stage — .NET 10 SDK
# ----------------------------------------------------------------------
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

# Copy nuget config + csproj first to leverage the Docker layer cache for restore.
COPY nuget.config ./
COPY src/Reliever.TierManagement.Stub/Reliever.TierManagement.Stub.csproj ./src/Reliever.TierManagement.Stub/

RUN dotnet restore ./src/Reliever.TierManagement.Stub/Reliever.TierManagement.Stub.csproj

# Copy the rest of the sources (tests are excluded via .dockerignore).
COPY src/ ./src/

RUN dotnet publish ./src/Reliever.TierManagement.Stub/Reliever.TierManagement.Stub.csproj \
        -c Release \
        -o /app/publish \
        --no-restore \
        /p:UseAppHost=false

# ----------------------------------------------------------------------
# Runtime stage — .NET 10 runtime + tini + socat for the /health shim
# ----------------------------------------------------------------------
FROM mcr.microsoft.com/dotnet/runtime:10.0 AS runtime

# tini = PID 1 reaper. socat = TCP↔stdio bridge used for the health shim.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini socat ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=build /app/publish/ ./

# Health shim — socat listener + per-connection responder. Replies 200 OK on
# the COMPONENT_PORT iff the .NET worker PID is alive. Lives in the image
# (not in src/).
COPY deployment/local/health-shim.sh     /usr/local/bin/health-shim.sh
COPY deployment/local/health-respond.sh  /usr/local/bin/health-respond.sh
COPY deployment/local/entrypoint.sh      /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/health-shim.sh \
             /usr/local/bin/health-respond.sh \
             /usr/local/bin/entrypoint.sh

# Defaults — every value is overridable at runtime via env vars.
# Mode-B stub stays INACTIVE by default (DoD: inactive in production).
ENV STUB_Stub__Active=false \
    STUB_Stub__RabbitMq__HostName=rabbitmq \
    STUB_Stub__RabbitMq__Port=5672 \
    STUB_Stub__RabbitMq__UserName=guest \
    STUB_Stub__RabbitMq__Password=guest \
    STUB_Stub__RabbitMq__VirtualHost=/ \
    COMPONENT_PORT=20393 \
    DOTNET_RUNNING_IN_CONTAINER=true \
    DOTNET_GENERATE_ASPNET_CERTIFICATES=false

EXPOSE 20393

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
