using System.Diagnostics;
using System.Diagnostics.Metrics;

namespace Reliever.BeneficiaryDashboard.Bff.Telemetry;

/// <summary>
/// Shared OTel signal sources for CAP.CHN.001.DSH.
///
/// Mandatory tags on every signal (ADR-TECH-STRAT-005):
///   capability_id = CAP.CHN.001.DSH
///   zone          = chn
///   deployable    = reliever-chn
///   environment   = (branch slug — from Telemetry:Environment / ASPNETCORE_ENVIRONMENT)
///
/// ActivitySource spans the inbound RVT → policy → command → aggregate
/// path. Each consumer wraps Consume() in a child span of the
/// MassTransit-instrumented parent span (W3C traceparent propagated via
/// RabbitMQ headers thanks to MassTransit.UseOpenTelemetry()).
/// </summary>
public static class DashboardTelemetry
{
    public const string SourceName = "Reliever.BeneficiaryDashboard.Bff";
    public const string CapabilityId = "CAP.CHN.001.DSH";
    public const string Zone = "chn";
    public const string Deployable = "reliever-chn";

    public static readonly ActivitySource Activity = new(SourceName);
    public static readonly Meter Meter = new(SourceName);

    // ── Per-policy ingest rate ───────────────────────────────────────────
    private static readonly Counter<long> PolicyIngestCounter = Meter.CreateCounter<long>(
        name: "chn_dsh_policy_ingest_total",
        description: "Number of upstream RVTs consumed by a dashboard policy.");

    public static void RecordPolicyIngest(string policy, string outcome)
    {
        PolicyIngestCounter.Add(1,
            new KeyValuePair<string, object?>("policy", policy),
            new KeyValuePair<string, object?>("outcome", outcome),
            new KeyValuePair<string, object?>("capability_id", CapabilityId));
    }

    // ── Per-subscription DLQ depth ────────────────────────────────────────
    // MassTransit increments this counter every time the consumer throws —
    // its retry policy will surface those to the *_error queue (DLQ
    // convention). The counter is a *cumulative* count of DLQ-bound
    // messages; the actual depth comes from the broker (Prometheus
    // rabbitmq_exporter), but the counter gives an in-process signal too.
    private static readonly Counter<long> DlqCounter = Meter.CreateCounter<long>(
        name: "chn_dsh_dlq_total",
        description: "Number of inbound RVTs routed to the DLQ (payload-shape errors).");

    public static void RecordDlq(string subscription, string reason)
    {
        DlqCounter.Add(1,
            new KeyValuePair<string, object?>("subscription", subscription),
            new KeyValuePair<string, object?>("reason", reason),
            new KeyValuePair<string, object?>("capability_id", CapabilityId));
    }
}
