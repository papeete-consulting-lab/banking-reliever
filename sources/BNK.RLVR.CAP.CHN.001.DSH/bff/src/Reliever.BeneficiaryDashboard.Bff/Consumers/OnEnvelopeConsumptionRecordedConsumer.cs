using MassTransit;
using Reliever.BeneficiaryDashboard.Bff.Application.Commands;
using Reliever.BeneficiaryDashboard.Bff.Contracts.UpstreamEvents;
using Reliever.BeneficiaryDashboard.Bff.Domain.Validators;
using Reliever.BeneficiaryDashboard.Bff.Telemetry;

namespace Reliever.BeneficiaryDashboard.Bff.Consumers;

/// <summary>
/// POL.CHN.001.DSH.ON_ENVELOPE_CONSUMPTION_RECORDED — listens to
/// RVT.BSP.004.CONSUMPTION_RECORDED on bsp.004.env-events
/// (binding EVT.BSP.004.ENVELOPE_CONSUMED.RVT.BSP.004.CONSUMPTION_RECORDED).
///
/// Notes on mapping (see README A5):
///   - The upstream schema does not carry 'merchant_label'; the dashboard
///     records it as null until CAP.BSP.004.ENV ships it.
///   - The upstream schema carries consumed_amount_after + remaining_amount
///     but not allocated_amount; we derive allocated = consumed_after + remaining.
///   - Currency is not on the upstream schema today either; we default to
///     "EUR" until the producer schema is extended.
/// </summary>
public sealed class OnEnvelopeConsumptionRecordedConsumer : IConsumer<EnvelopeConsumptionRecordedRaw>
{
    public const string PolicyName = "POL.CHN.001.DSH.ON_ENVELOPE_CONSUMPTION_RECORDED";
    public const string Subscription = "envelope-consumed";
    public const string DefaultCurrency = "EUR";

    private readonly UpstreamSchemaValidator _schema;
    private readonly DashboardCommandHandlers _handlers;
    private readonly ILogger<OnEnvelopeConsumptionRecordedConsumer> _logger;

    public OnEnvelopeConsumptionRecordedConsumer(
        UpstreamSchemaValidator schema,
        DashboardCommandHandlers handlers,
        ILogger<OnEnvelopeConsumptionRecordedConsumer> logger)
    {
        _schema = schema;
        _handlers = handlers;
        _logger = logger;
    }

    public Task Consume(ConsumeContext<EnvelopeConsumptionRecordedRaw> context)
    {
        using var activity = DashboardTelemetry.Activity.StartActivity(
            "policy.on_envelope_consumption_recorded",
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

        if (!_schema.ValidateEnvelopeConsumption(parsed, out var schemaError))
        {
            DashboardTelemetry.RecordDlq(Subscription, "schema_violation");
            throw new InvalidOperationException(
                $"RVT.BSP.004.CONSUMPTION_RECORDED schema validation failed: {schemaError}. " +
                "Routing to DLQ.");
        }

        var payload = ConsumerSupport.Deserialize<EnvelopeConsumptionRecordedPayload>(raw);

        var allocated = payload.ConsumedAmountAfter + payload.RemainingAmount;
        var transactionId = payload.TransactionId
                            ?? payload.CausationEventId
                            ?? payload.EventId; // last-resort fallback so the feed always has a row id

        var cmd = new RecordEnvelopeConsumptionCommand(
            CaseId: payload.CaseId,
            EventId: payload.EventId,
            EnvelopeId: payload.AllocationId,
            Category: payload.Category,
            TransactionId: transactionId,
            Amount: payload.Amount,
            Currency: DefaultCurrency,
            MerchantLabel: null,
            AllocatedAmount: allocated,
            ConsumedAmount: payload.ConsumedAmountAfter,
            AvailableAmount: payload.RemainingAmount,
            RecordedAt: payload.OccurredAt);

        var outcome = _handlers.Handle(cmd);
        activity?.SetTag("outcome", outcome.ToString());
        DashboardTelemetry.RecordPolicyIngest(PolicyName, outcome.ToString());

        _logger.LogInformation(
            "ON_ENVELOPE_CONSUMPTION_RECORDED case={CaseId} event={EventId} envelope={EnvelopeId} amount={Amount} outcome={Outcome}",
            cmd.CaseId, cmd.EventId, cmd.EnvelopeId, cmd.Amount, outcome);

        return Task.CompletedTask;
    }
}

public sealed record EnvelopeConsumptionRecordedRaw;
