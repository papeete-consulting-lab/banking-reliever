using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Reliever.TierManagement.Stub;

// BNK.RLVR.CAP.BSP.001.TIE — Tier Management — Development Stub
//
// Mode B (contract-stub) per ADR-TECH-STRAT-001:
//   - publishes ONLY the resource event BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED (Rule 2)
//   - on a topic exchange owned by BNK.RLVR.CAP.BSP.001.TIE (Rule 1, 5)
//   - routing key: BNK.RLVR.EVT.BSP.001.TIER_UPGRADED.BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED (Rule 4)
//   - payload form: domain event DDD (Rule 3)
//   - every payload validated against the runtime JSON Schema before publishing
//   - inactive by default; activate via STUB_ACTIVE=true (Definition of Done — inactive in production)

var builder = Host.CreateApplicationBuilder(args);

// Layered configuration: appsettings.json (defaults) → config/stub.json (overrides) → env vars (deployment).
var stubConfigPath = Path.Combine(AppContext.BaseDirectory, "config", "stub.json");
if (File.Exists(stubConfigPath))
{
    builder.Configuration.AddJsonFile(stubConfigPath, optional: true, reloadOnChange: true);
}
builder.Configuration.AddEnvironmentVariables(prefix: "STUB_");
builder.Configuration.AddEnvironmentVariables();

builder.Services.Configure<StubOptions>(builder.Configuration.GetSection("Stub"));
builder.Services.AddSingleton<SchemaValidator>();
builder.Services.AddSingleton<PayloadFactory>();
builder.Services.AddHostedService<Worker>();

var host = builder.Build();
await host.RunAsync();
