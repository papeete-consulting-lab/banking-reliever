using MassTransit;
using Reliever.BeneficiaryDashboard.Bff.Application.Commands;
using Reliever.BeneficiaryDashboard.Bff.Contracts.UpstreamEvents;
using Reliever.BeneficiaryDashboard.Bff.Domain.Validators;
using Reliever.BeneficiaryDashboard.Bff.Telemetry;

namespace Reliever.BeneficiaryDashboard.Bff.Consumers;

/// <summary>
/// POL.CHN.001.DSH.ON_TIER_UPGRADE_RECORDED — listens to
/// RVT.BSP.001.TIER_UPGRADE_RECORDED on bsp.001.tie-events
/// (binding EVT.BSP.001.TIER_UPGRADED.RVT.BSP.001.TIER_UPGRADE_RECORDED).
///
/// Tier downgrades (RVT.BSP.001.TIER_DOWNGRADE_RECORDED) are NOT
/// subscribed-to here — see policies.yaml.open_question and the
/// roadmap "Tier downgrades intentionally invisible" framing decision.
/// </summary>
public sealed class OnTierUpgradeRecordedConsumer : IConsumer<TierUpgradeRecordedRaw>
{
    public const string PolicyName = "POL.CHN.001.DSH.ON_TIER_UPGRADE_RECORDED";
    public const string Subscription = "tier-upgraded";

    private readonly UpstreamSchemaValidator _schema;
    private readonly DashboardCommandHandlers _handlers;
    private readonly ILogger<OnTierUpgradeRecordedConsumer> _logger;

    public OnTierUpgradeRecordedConsumer(
        UpstreamSchemaValidator schema,
        DashboardCommandHandlers handlers,
        ILogger<OnTierUpgradeRecordedConsumer> logger)
    {
        _schema = schema;
        _handlers = handlers;
        _logger = logger;
    }

    public Task Consume(ConsumeContext<TierUpgradeRecordedRaw> context)
    {
        using var activity = DashboardTelemetry.Activity.StartActivity(
            "policy.on_tier_upgrade_recorded",
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

        if (!_schema.ValidateTier(parsed, out var schemaError))
        {
            DashboardTelemetry.RecordDlq(Subscription, "schema_violation");
            throw new InvalidOperationException(
                $"RVT.BSP.001.TIER_UPGRADE_RECORDED schema validation failed: {schemaError}. " +
                "Routing to DLQ.");
        }

        var payload = ConsumerSupport.Deserialize<TierUpgradeRecordedPayload>(raw);

        var cmd = new SynchronizeTierCommand(
            CaseId: payload.CaseId,
            EventId: payload.EventId,
            PreviousTierCode: payload.Transition.FromTierCode,
            CurrentTierCode: payload.Transition.ToTierCode,
            UpgradedAt: payload.OccurredAt);

        var outcome = _handlers.Handle(cmd);
        activity?.SetTag("outcome", outcome.ToString());
        DashboardTelemetry.RecordPolicyIngest(PolicyName, outcome.ToString());

        _logger.LogInformation(
            "ON_TIER_UPGRADE_RECORDED case={CaseId} event={EventId} from={From} to={To} outcome={Outcome}",
            cmd.CaseId, cmd.EventId, cmd.PreviousTierCode, cmd.CurrentTierCode, outcome);

        return Task.CompletedTask;
    }
}

public sealed record TierUpgradeRecordedRaw;
