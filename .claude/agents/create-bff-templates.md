# BFF Code Templates

> **Layout note**: the deployment templates (`Dockerfile`, `docker-compose.yml`,
> `.env`, `platform.compose.yml`, `README.md`) render to
> `sources/{CAP_ID}/bff/deployment/local/` — NOT to the component root.
> `appsettings*.json` stays at its current location (the component root).

Placeholders: `{CapId}`, `{capability-id}`, `{CapabilityIdDot}`, `{ZoneAbbrev}`,
`{zone-abbrev}`, `{Namespace}`, `{COMPONENT_PORT}`, `{FRONTEND_PORT}`, `{branch}`.

`{COMPONENT_PORT}` is deterministic from `capability_id` (kind=`bff`) per the
Deployment contract. `{FRONTEND_PORT}` is the same deterministic formula
(kind=`frontend`) and is used ONLY for the CORS allowlist.

Per-L3 placeholders: `{L3Name}` (PascalCase), `{l3-id}` (lowercase), `{l3-path}` (URL segment).
Per-event placeholders: `{EventName}` (PascalCase), `{business-event-name}` (kebab),
`{SourceExchange}`, `{QueueName}`, `{RoutingKeyFilter}`.

---

## {CapId}Bff.csproj

```xml
<Project Sdk="Microsoft.NET.Sdk.Web">

  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <RootNamespace>{Namespace}</RootNamespace>
    <AssemblyName>{CapId}Bff</AssemblyName>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="MassTransit.RabbitMQ" Version="8.*" />
    <PackageReference Include="OpenTelemetry.Extensions.Hosting" Version="1.*" />
    <PackageReference Include="OpenTelemetry.Instrumentation.AspNetCore" Version="1.*" />
    <PackageReference Include="OpenTelemetry.Instrumentation.Http" Version="1.*" />
    <PackageReference Include="OpenTelemetry.Exporter.OpenTelemetryProtocol" Version="1.*" />
    <PackageReference Include="Microsoft.Extensions.Caching.Memory" Version="9.*" />
  </ItemGroup>

</Project>
```

---

## nuget.config

```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <clear />
    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />
  </packageSources>
</configuration>
```

---

## appsettings.json

```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore": "Warning",
      "MassTransit": "Information"
    }
  },
  "RabbitMQ": {
    "Host": "localhost",
    "Port": 5672,
    "VirtualHost": "{capability-id}",
    "Username": "admin",
    "Password": "password"
  },
  "Telemetry": {
    "ServiceName": "{capability-id}-bff",
    "OtlpEndpoint": "http://localhost:4317"
  }
}
```

---

## appsettings.Development.json

```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Debug",
      "MassTransit": "Debug"
    }
  },
  "RabbitMQ": {
    "Host": "rabbitmq",
    "VirtualHost": "{capability-id}",
    "Username": "guest",
    "Password": "guest"
  },
  "Kestrel": {
    "Endpoints": {
      "Http": {
        "Url": "http://+:8080"
      }
    }
  }
}
```

---

## Program.cs

```csharp
using {Namespace}.Cache;
using {Namespace}.Consumers;
using {Namespace}.Publishers;
using {Namespace}.Endpoints;
using {Namespace}.Telemetry;

var builder = WebApplication.CreateBuilder(args);

// ── Telemetry ────────────────────────────────────────────────────────────────
builder.Services.AddTelemetry(builder.Configuration, builder.Environment);

// ── State cache (singleton — holds latest event-driven state per L3) ─────────
builder.Services.AddSingleton<{CapId}StateCache>();

// ── Publishers ───────────────────────────────────────────────────────────────
// {list each publisher registration}
// builder.Services.AddScoped<{EventName}Publisher>();

// ── MassTransit / RabbitMQ ───────────────────────────────────────────────────
builder.Services.AddMassTransit(x =>
{
    // Consumers (one per subscribed event type)
    // {list each consumer registration}
    // x.AddConsumer<{EventName}Consumer>();

    x.UsingRabbitMq((ctx, cfg) =>
    {
        var rabbit = builder.Configuration.GetSection("RabbitMQ");
        cfg.Host(rabbit["Host"], ushort.Parse(rabbit["Port"]!), rabbit["VirtualHost"], h =>
        {
            h.Username(rabbit["Username"]!);
            h.Password(rabbit["Password"]!);
        });

        // OTel trace propagation through RabbitMQ headers
        cfg.UseOpenTelemetry();

        // Subscriptions (one receive endpoint per consumed event queue)
        // {list each receive endpoint}
        // cfg.ReceiveEndpoint("{QueueName}", e =>
        // {
        //     e.Bind("{SourceExchange}", b =>
        //     {
        //         b.ExchangeType = "topic";
        //         b.RoutingKey = "{RoutingKeyFilter}";
        //     });
        //     e.ConfigureConsumer<{EventName}Consumer>(ctx);
        // });

        // BFF own exchange (for events published by this BFF)
        cfg.Message<object>(x => x.SetEntityName("{capability-id}.exchange"));

        cfg.ConfigureEndpoints(ctx);
    });
});

// ── Authentication ────────────────────────────────────────────────────────────
// TODO: wire OpenFGA middleware — decided in L2 tactical ADR (CAP.{ZoneAbbrev}.XXX)
// builder.Services.AddAuthentication(...).AddJwtBearer(...);
// builder.Services.AddAuthorization(...);

// ── CORS (for frontend hosted on different origin in dev) ────────────────────
builder.Services.AddCors(options =>
    options.AddDefaultPolicy(policy =>
        policy.AllowAnyOrigin().AllowAnyHeader().AllowAnyMethod()));

var app = builder.Build();

app.UseCors();
// app.UseAuthentication();
// app.UseAuthorization();

// ── Endpoints ─────────────────────────────────────────────────────────────────
// {list each endpoint group registration}
// app.Map{L3Name}Endpoints();

// ── Health ────────────────────────────────────────────────────────────────────
app.MapGet("/health", () => Results.Ok(new { status = "ok", capability = "{CapabilityIdDot}" }));

app.Run();
```

---

## Telemetry/TelemetrySetup.cs

```csharp
using OpenTelemetry.Metrics;
using OpenTelemetry.Trace;
using OpenTelemetry.Resources;

namespace {Namespace}.Telemetry;

public static class TelemetrySetup
{
    // Mandatory tags on every OTel signal (TECH-STRAT-005)
    public const string CapabilityId  = "{CapabilityIdDot}";
    public const string Zone          = "{zone-abbrev}";
    public const string Deployable    = "<product>-{zone-abbrev}";

    public static IServiceCollection AddTelemetry(
        this IServiceCollection services,
        IConfiguration config,
        IHostEnvironment env)
    {
        var serviceName = config["Telemetry:ServiceName"] ?? "{capability-id}-bff";
        var otlpEndpoint = config["Telemetry:OtlpEndpoint"] ?? "http://localhost:4317";

        var resourceBuilder = ResourceBuilder.CreateDefault()
            .AddService(serviceName)
            .AddAttributes(new Dictionary<string, object>
            {
                ["capability_id"] = CapabilityId,
                ["zone"]          = Zone,
                ["deployable"]    = Deployable,
                ["environment"]   = env.EnvironmentName,
            });

        services.AddOpenTelemetry()
            .WithTracing(tracing => tracing
                .SetResourceBuilder(resourceBuilder)
                .AddAspNetCoreInstrumentation()
                .AddHttpClientInstrumentation()
                .AddSource("MassTransit")
                .AddOtlpExporter(o => o.Endpoint = new Uri(otlpEndpoint)))
            .WithMetrics(metrics => metrics
                .SetResourceBuilder(resourceBuilder)
                .AddAspNetCoreInstrumentation()
                .AddRuntimeInstrumentation()
                .AddOtlpExporter(o => o.Endpoint = new Uri(otlpEndpoint)));

        return services;
    }
}
```

---

## Cache/{CapId}StateCache.cs

```csharp
namespace {Namespace}.Cache;

/// <summary>
/// In-memory event-driven state for {CapabilityIdDot}.
/// Updated by RabbitMQ consumers. Never stores PII.
/// All state is purgeable — the BFF reconstructs from incoming events.
/// </summary>
public sealed class {CapId}StateCache
{
    private readonly object _lock = new();

    // ── One nested state record per L3 ──────────────────────────────────────
    // Generate one State class per L3, with fields derived from the tactical ADR
    // payload shape (or from the FUNC ADR events if no tactical ADR exists).
    //
    // Example for TAB:
    // public sealed record TabState(
    //     decimal Score,
    //     string  Tier,
    //     string  TierTrend,
    //     decimal EnvelopeAvailable,
    //     decimal EnvelopeTotal,
    //     string  ETag,
    //     DateTime UpdatedAt);
    //
    // {L3State records — generate one per L3}

    // ── State holders ────────────────────────────────────────────────────────
    // {L3Name}State? _{l3Name}State;
    // public {L3Name}State? Get{L3Name}State() => _{l3Name}State;

    // ── Update methods (called by consumers) ─────────────────────────────────
    // Generate one update method per consumed event type.
    // Each method must:
    //   1. Acquire _lock
    //   2. Update the relevant field(s) on the relevant L3 state
    //   3. Recompute ETag (Guid.NewGuid().ToString("N")[..8])
    //   4. Set UpdatedAt = DateTime.UtcNow
    //
    // Example:
    // public void OnScoreRecalculé(decimal newScore)
    // {
    //     lock (_lock)
    //     {
    //         var current = _tabState ?? new TabState(0, "", "stable", 0, 0, "", default);
    //         _tabState = current with
    //         {
    //             Score     = newScore,
    //             ETag      = Guid.NewGuid().ToString("N")[..8],
    //             UpdatedAt = DateTime.UtcNow,
    //         };
    //     }
    // }
}
```

---

## Endpoints/{L3Name}Endpoints.cs

```csharp
using {Namespace}.Cache;
using {Namespace}.Publishers;

namespace {Namespace}.Endpoints;

public static class {L3Name}Endpoints
{
    // SLO: {SLO targets from tactical ADR, or "see ADR-TECH-TACT-NNN" if known}
    public static IEndpointRouteBuilder Map{L3Name}Endpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/{zone-abbrev}/{capability-id}/{l3-id}");

        // GET /snapshot — cacheable state with ETag support
        group.MapGet("/snapshot", GetSnapshot)
            .WithName("{L3Name}GetSnapshot")
            .WithDescription("Returns the current {L3Name} state. Supports ETag/304.");

        // POST /view — signals a user consultation (fires a business event)
        // Remove if this L3 does not produce a 'Consulté' event
        group.MapPost("/view", RecordView)
            .WithName("{L3Name}RecordView");

        // Add further endpoints derived from the tactical ADR contract here.

        return app;
    }

    private static IResult GetSnapshot(
        {CapId}StateCache cache,
        HttpContext context)
    {
        var state = cache.Get{L3Name}State();
        if (state is null)
            return Results.NotFound();

        // ETag / 304 support (TECH-STRAT-003 + ADR-TECH-TACT-NNN)
        var ifNoneMatch = context.Request.Headers.IfNoneMatch.ToString().Trim('"');
        if (ifNoneMatch == state.ETag)
            return Results.StatusCode(304);

        context.Response.Headers.ETag         = $"\"{state.ETag}\"";
        context.Response.Headers.CacheControl = "no-store";

        return Results.Ok(state);
    }

    private static async Task<IResult> RecordView(
        // Inject the relevant publisher for the business event produced on view
        // {EventName}Publisher publisher,
        CancellationToken ct)
    {
        // await publisher.PublishAsync(ct);
        return Results.NoContent();
    }
}
```

---

## Consumers/{EventName}Consumer.cs

```csharp
using MassTransit;
using {Namespace}.Cache;
using {Namespace}.Contracts.Events;

namespace {Namespace}.Consumers;

/// <summary>
/// Subscribes to {EventName} events emitted by {SourceCapabilityId}.
/// Exchange: {SourceExchange} — routing key filter: {RoutingKeyFilter}
/// Updates the in-memory state cache on receipt.
/// </summary>
public sealed class {EventName}Consumer : IConsumer<{EventName}Event>
{
    private readonly {CapId}StateCache _cache;
    private readonly ILogger<{EventName}Consumer> _logger;

    public {EventName}Consumer({CapId}StateCache cache, ILogger<{EventName}Consumer> logger)
    {
        _cache  = cache;
        _logger = logger;
    }

    public Task Consume(ConsumeContext<{EventName}Event> context)
    {
        // Map the event payload to the cache update.
        // Only extract non-PII fields (enforce exclusions from tactical ADR).
        // _cache.On{EventName}(context.Message.{RelevantField});

        _logger.LogInformation(
            "Handled {EventName} for capability {CapabilityId}",
            nameof({EventName}Event),
            "{CapabilityIdDot}");

        return Task.CompletedTask;
    }
}
```

---

## Publishers/{EventName}Publisher.cs

```csharp
using MassTransit;
using {Namespace}.Contracts.Events;

namespace {Namespace}.Publishers;

/// <summary>
/// Publishes {EventName} to the BFF own exchange: {capability-id}.exchange
/// Routing key: {BusinessEventName}.{ResourceEventName}
/// Called by endpoint handlers when a frontend interaction triggers a business event.
/// </summary>
public sealed class {EventName}Publisher
{
    private readonly IBus _bus;
    private readonly ILogger<{EventName}Publisher> _logger;

    public {EventName}Publisher(IBus bus, ILogger<{EventName}Publisher> logger)
    {
        _bus    = bus;
        _logger = logger;
    }

    public async Task PublishAsync(CancellationToken ct = default)
    {
        var @event = new {EventName}Event
        {
            OccurredAt = DateTime.UtcNow,
            // Populate fields from context (injected into method signature if needed)
        };

        await _bus.Publish(@event, ct);

        _logger.LogInformation(
            "Published {EventName} from capability {CapabilityId}",
            nameof({EventName}Event),
            "{CapabilityIdDot}");
    }
}
```

---

## Contracts/Events/{EventName}Event.cs

```csharp
namespace {Namespace}.Contracts.Events;

/// <summary>
/// Contract for {EventName}.
/// Routing key: {BusinessEventName}.{ResourceEventName} (TECH-STRAT-001)
/// {If consumed: Emitted by {SourceCapabilityId} on exchange {SourceExchange}}
/// {If produced: Published by {CapabilityIdDot} on exchange {capability-id}.exchange}
/// </summary>
public sealed record {EventName}Event
{
    public DateTime OccurredAt { get; init; }

    // Add fields derived from the FUNC ADR event definition or tactical ADR payload.
    // Never include PII fields excluded by the tactical ADR.
}
```

---

## Dockerfile

```dockerfile
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /app

COPY *.csproj ./
RUN dotnet restore

COPY . ./
RUN dotnet publish -c Release -o /out --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
WORKDIR /app
COPY --from=build /out ./

ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

LABEL capability_id="{CapabilityIdDot}"
LABEL zone="{zone-abbrev}"
LABEL deployable="<product>-{zone-abbrev}"

ENTRYPOINT ["dotnet", "{CapId}Bff.dll"]
```

---

## docker-compose.yml

```yaml
# Component-only compose for {capability-id}-bff.
# Joins the external `<product>-platform` Docker network — RabbitMQ (and any DB)
# is provided by the platform installation, NOT bundled here.
# Renders to: sources/{CAP_ID}/bff/deployment/local/docker-compose.yml
services:
  {capability-id}-bff:
    image: {capability-id}-bff:dev
    build: .
    env_file: .env
    networks: [<product>-platform]
    ports: ["${COMPONENT_PORT}:8080"]
    healthcheck:
      test: ["CMD","curl","-fsS","http://localhost:8080/health"]
      interval: 10s
      retries: 6
networks:
  <product>-platform: { external: true }
```

---

## .env

```
COMPONENT_PORT={COMPONENT_PORT}
AMQP_URL=amqp://guest:guest@rabbitmq:5672/
BRANCH={branch}
CORS_ALLOWED_ORIGINS=http://localhost:{FRONTEND_PORT}
```

---

## platform.compose.yml

```yaml
# Stand-in platform for local dev / tests — NOT the real platform.
services:
  rabbitmq:
    image: rabbitmq:3.13-management-alpine
    ports: ["5672:5672", "15672:15672"]
    environment: { RABBITMQ_DEFAULT_USER: guest, RABBITMQ_DEFAULT_PASS: guest }
    healthcheck: { test: ["CMD","rabbitmq-diagnostics","-q","ping"], interval: 10s, retries: 6 }
networks:
  default:
    name: <product>-platform
    external: true
```
