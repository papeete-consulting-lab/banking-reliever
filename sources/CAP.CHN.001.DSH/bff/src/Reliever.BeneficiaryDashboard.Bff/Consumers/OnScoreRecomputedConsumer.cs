using MassTransit;
using Reliever.BeneficiaryDashboard.Bff.Application.Commands;
using Reliever.BeneficiaryDashboard.Bff.Contracts.UpstreamEvents;
using Reliever.BeneficiaryDashboard.Bff.Domain;
using Reliever.BeneficiaryDashboard.Bff.Domain.Validators;
using Reliever.BeneficiaryDashboard.Bff.Telemetry;

namespace Reliever.BeneficiaryDashboard.Bff.Consumers;

/// <summary>
/// POL.CHN.001.DSH.ON_SCORE_RECOMPUTED — listens to
/// RVT.BSP.001.CURRENT_SCORE_RECOMPUTED on exchange bsp.001.sco-events
/// (binding key EVT.BSP.001.SCORE_RECOMPUTED.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED).
///
/// Behaviour:
///   1. Reads the raw JSON body.
///   2. PII scan (INV.DSH.001) → throws if a deny-listed property is detected (→ DLQ).
///   3. JSON Schema validation against the upstream producer's published schema
///      (process/CAP.BSP.001.SCO/schemas/…) → throws on shape mismatch (→ DLQ).
///   4. Deserialises into <see cref="ScoreRecomputedPayload"/>.
///   5. Maps to <see cref="SynchronizeScoreCommand"/> per the mapping rule
///      declared in process/CAP.CHN.001.DSH/policies.yaml:ON_SCORE_RECOMPUTED.
///   6. Handler returns Applied / EventAlreadyProcessed / StaleEvent —
///      the latter two are ack-and-dropped (silent absorb per the error
///      handling in policies.yaml).
/// </summary>
public sealed class OnScoreRecomputedConsumer : IConsumer<ScoreRecomputedRaw>
{
    public const string PolicyName = "POL.CHN.001.DSH.ON_SCORE_RECOMPUTED";
    public const string Subscription = "score-recomputed";

    private readonly UpstreamSchemaValidator _schema;
    private readonly DashboardCommandHandlers _handlers;
    private readonly ILogger<OnScoreRecomputedConsumer> _logger;

    public OnScoreRecomputedConsumer(
        UpstreamSchemaValidator schema,
        DashboardCommandHandlers handlers,
        ILogger<OnScoreRecomputedConsumer> logger)
    {
        _schema = schema;
        _handlers = handlers;
        _logger = logger;
    }

    public Task Consume(ConsumeContext<ScoreRecomputedRaw> context)
    {
        using var activity = DashboardTelemetry.Activity.StartActivity(
            "policy.on_score_recomputed",
            System.Diagnostics.ActivityKind.Consumer);
        activity?.SetTag("capability_id", DashboardTelemetry.CapabilityId);
        activity?.SetTag("policy", PolicyName);

        var (parsed, raw) = ConsumerSupport.ReadRawJson(context);

        if (!PiiClassificationScanner.IsPiiFree(parsed, out var piiPath))
        {
            DashboardTelemetry.RecordDlq(Subscription, "pii_violation");
            throw new InvalidOperationException(
                $"INV.DSH.001 — payload carries a PII-classified field at {piiPath}. " +
                "Routing to DLQ.");
        }

        if (!_schema.ValidateScore(parsed, out var schemaError))
        {
            DashboardTelemetry.RecordDlq(Subscription, "schema_violation");
            throw new InvalidOperationException(
                $"RVT.BSP.001.CURRENT_SCORE_RECOMPUTED schema validation failed: {schemaError}. " +
                "Routing to DLQ.");
        }

        var payload = ConsumerSupport.Deserialize<ScoreRecomputedPayload>(raw);

        var cmd = new SynchronizeScoreCommand(
            CaseId: payload.CaseId,
            // The mapping rule in policies.yaml maps idempotency on upstream.event_id.
            // For SCO, the wire schema carries event_id under 'trigger.event_id' (the
            // upstream RVT that drove the recomputation). We use envelope.message_id
            // for end-to-end at-this-channel idempotency — see README A4.
            EventId: payload.Envelope.MessageId,
            ScoreValue: payload.ScoreValue,
            DeltaScore: payload.DeltaScore,
            RecomputedAt: payload.ComputationTimestamp,
            ModelVersion: payload.ModelVersion);

        var outcome = _handlers.Handle(cmd);
        activity?.SetTag("outcome", outcome.ToString());
        DashboardTelemetry.RecordPolicyIngest(PolicyName, outcome.ToString());

        _logger.LogInformation(
            "ON_SCORE_RECOMPUTED case={CaseId} event={EventId} outcome={Outcome}",
            cmd.CaseId, cmd.EventId, outcome);

        return Task.CompletedTask;
    }
}

/// <summary>
/// Marker message type so MassTransit can dispatch the receive endpoint
/// to the typed consumer. The raw JSON body is read off the
/// <see cref="MessageBody"/> payload inside the consumer.
/// </summary>
public sealed record ScoreRecomputedRaw;
