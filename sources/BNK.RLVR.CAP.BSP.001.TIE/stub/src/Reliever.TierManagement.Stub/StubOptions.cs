namespace Reliever.TierManagement.Stub;

/// <summary>
/// Strongly-typed configuration for the BNK.RLVR.CAP.BSP.001.TIE development stub.
/// Bound from the "Stub" section of appsettings.json + config/stub.json + env vars.
/// </summary>
public sealed class StubOptions
{
    /// <summary>
    /// Master switch. When false (default), the stub starts but publishes nothing.
    /// MUST be false in production environments. Activate via env var STUB_ACTIVE=true
    /// (or STUB_Stub__Active=true depending on prefix configuration).
    /// </summary>
    public bool Active { get; set; } = false;

    /// <summary>
    /// Cadence of publication (events per minute). Default range 1..10. Outside that
    /// range requires explicit override via AllowOutOfRangeCadence=true.
    /// </summary>
    public double EventsPerMinute { get; set; } = 6;

    /// <summary>
    /// Explicit override required to allow EventsPerMinute outside the [1, 10] range.
    /// Per Definition of Done: 1..10/min default; outside requires explicit override.
    /// </summary>
    public bool AllowOutOfRangeCadence { get; set; } = false;

    /// <summary>
    /// Configurable list of simulated case identifiers (case_id).
    /// The stub cycles through them and assigns a tier-progression state to each.
    /// </summary>
    public List<string> CaseIds { get; set; } = new()
    {
        "CASE-2026-000001",
        "CASE-2026-000002",
        "CASE-2026-000003",
        "CASE-2026-000004",
        "CASE-2026-000005"
    };

    /// <summary>
    /// Ordered list of tier codes describing the upward progression path
    /// (e.g. T0 → T1 → T2 → T3). The last tier is treated as programme exit.
    /// </summary>
    public List<string> TierProgression { get; set; } = new() { "T0", "T1", "T2", "T3" };

    public RabbitMqOptions RabbitMq { get; set; } = new();
    public BusOptions Bus { get; set; } = new();
    public SchemaOptions Schema { get; set; } = new();
}

public sealed class RabbitMqOptions
{
    public string HostName { get; set; } = "localhost";
    public int Port { get; set; } = 45381;
    public string UserName { get; set; } = "guest";
    public string Password { get; set; } = "guest";
    public string VirtualHost { get; set; } = "/";
}

public sealed class BusOptions
{
    /// <summary>
    /// Topic exchange owned by BNK.RLVR.CAP.BSP.001.TIE (ADR-TECH-STRAT-001 Rule 1, 5).
    /// Only this capability publishes on it.
    /// </summary>
    public string ExchangeName { get; set; } = "bsp.001.pal-events";

    /// <summary>
    /// Routing key for upward tier crossings (ADR-TECH-STRAT-001 Rule 4):
    /// {BusinessEventName}.{ResourceEventName}.
    /// </summary>
    public string RoutingKey { get; set; } = "BNK.RLVR.EVT.BSP.001.TIER_UPGRADED.BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED";
}

public sealed class SchemaOptions
{
    /// <summary>
    /// Path to the runtime JSON Schema, relative to the binary working directory.
    /// Loaded once at startup; every outgoing payload is validated against it.
    /// </summary>
    public string RuntimeSchemaPath { get; set; } = "schemas/BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED.schema.json";
}
