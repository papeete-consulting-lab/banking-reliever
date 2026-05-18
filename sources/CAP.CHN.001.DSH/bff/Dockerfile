# syntax=docker/dockerfile:1.7
# Multi-stage build for Reliever.BeneficiaryDashboard.Bff (CAP.CHN.001.DSH).
# Notes:
#   - Upstream RVT JSON Schemas live OUTSIDE this folder (process/CAP.BSP.*/schemas/).
#     The .csproj <Content Include="..\..\..\..\..\process\..."/> relies on the repo
#     root being the build context. Run from the repo root:
#       docker build -f sources/CAP.CHN.001.DSH/bff/Dockerfile -t chn-001-dsh-bff:dev .

FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /repo

# Copy project + read-only process schemas (mounted at the right relative path).
COPY sources/CAP.CHN.001.DSH/bff /repo/sources/CAP.CHN.001.DSH/bff
COPY process/CAP.BSP.001.SCO/schemas /repo/process/CAP.BSP.001.SCO/schemas
COPY process/CAP.BSP.001.TIE/schemas /repo/process/CAP.BSP.001.TIE/schemas
COPY process/CAP.BSP.004.ENV/schemas /repo/process/CAP.BSP.004.ENV/schemas

WORKDIR /repo/sources/CAP.CHN.001.DSH/bff
RUN dotnet restore Reliever.BeneficiaryDashboard.Bff.sln
RUN dotnet publish src/Reliever.BeneficiaryDashboard.Bff/Reliever.BeneficiaryDashboard.Bff.csproj \
    -c Release -o /out --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
WORKDIR /app
COPY --from=build /out ./

ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

LABEL capability_id="CAP.CHN.001.DSH"
LABEL zone="chn"
LABEL deployable="reliever-chn"

ENTRYPOINT ["dotnet", "Reliever.BeneficiaryDashboard.Bff.dll"]
