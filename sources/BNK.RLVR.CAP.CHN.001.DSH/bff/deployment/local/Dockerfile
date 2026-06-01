# syntax=docker/dockerfile:1.7
# Multi-stage build for Reliever.BeneficiaryDashboard.Bff (BNK.RLVR.CAP.CHN.001.DSH).
# Universal build artefact per the Deployment contract (CLAUDE.md § "Deployment
# contract (local + dev)"): the same image is used by `deployment/local/` and
# pulled by `deployment/dev/` from ECR (delivery/registry).
#
# Notes:
#   - The upstream RVT JSON Schemas the BFF validates against are VENDORED into
#     the project under src/Reliever.BeneficiaryDashboard.Bff/process-schemas/
#     (the process model itself lives upstream in reliever-knowledge, consumed
#     via `rlv-knowledge process`). They ship with the project copy below — no
#     separate process/ mount is needed.
#   - The build context is the REPO ROOT so the COPY path below resolves; this
#     mirrors the legacy Dockerfile contract.
#       docker build \
#         -f sources/BNK.RLVR.CAP.CHN.001.DSH/bff/deployment/local/Dockerfile \
#         -t chn-001-dsh-bff:dev .

FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /repo

# Copy the project (the vendored process-schemas/ travels with it).
COPY sources/BNK.RLVR.CAP.CHN.001.DSH/bff /repo/sources/BNK.RLVR.CAP.CHN.001.DSH/bff

WORKDIR /repo/sources/BNK.RLVR.CAP.CHN.001.DSH/bff
RUN dotnet restore Reliever.BeneficiaryDashboard.Bff.sln
RUN dotnet publish src/Reliever.BeneficiaryDashboard.Bff/Reliever.BeneficiaryDashboard.Bff.csproj \
    -c Release -o /out --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
WORKDIR /app
COPY --from=build /out ./

ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

LABEL capability_id="BNK.RLVR.CAP.CHN.001.DSH"
LABEL zone="chn"
LABEL deployable="reliever-chn"

# K8s/compose healthcheck hits /health — wired by the BFF Minimal API.
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD wget -qO- http://127.0.0.1:8080/health || exit 1

ENTRYPOINT ["dotnet", "Reliever.BeneficiaryDashboard.Bff.dll"]
