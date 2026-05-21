using Reliever.BeneficiaryDashboard.Bff.Domain;
using Reliever.BeneficiaryDashboard.Bff.Infrastructure.Persistence;

namespace Reliever.BeneficiaryDashboard.Bff.Application.Commands;

/// <summary>
/// Translates the internal command shapes into the aggregate's Apply*
/// methods. Lives in the Application layer per the standard hexagonal
/// split — the consumers (Presentation/adapter layer) call into here.
/// </summary>
public sealed class DashboardCommandHandlers
{
    private readonly IDashboardAggregateStore _store;
    private readonly TimeProvider _clock;

    public DashboardCommandHandlers(IDashboardAggregateStore store, TimeProvider clock)
    {
        _store = store;
        _clock = clock;
    }

    public CommandOutcome Handle(SynchronizeScoreCommand cmd)
    {
        var aggregate = _store.GetOrCreate(cmd.CaseId);
        return aggregate.ApplySynchronizeScore(
            eventId: cmd.EventId,
            scoreValue: cmd.ScoreValue,
            recomputedAt: cmd.RecomputedAt,
            now: _clock.GetUtcNow().UtcDateTime);
    }

    public CommandOutcome Handle(SynchronizeTierCommand cmd)
    {
        var aggregate = _store.GetOrCreate(cmd.CaseId);
        return aggregate.ApplySynchronizeTier(
            eventId: cmd.EventId,
            currentTierCode: cmd.CurrentTierCode,
            upgradedAt: cmd.UpgradedAt,
            now: _clock.GetUtcNow().UtcDateTime);
    }

    public CommandOutcome Handle(RecordEnvelopeConsumptionCommand cmd)
    {
        var aggregate = _store.GetOrCreate(cmd.CaseId);
        return aggregate.ApplyRecordEnvelopeConsumption(
            eventId: cmd.EventId,
            envelopeId: cmd.EnvelopeId,
            transactionId: cmd.TransactionId,
            category: cmd.Category,
            amount: cmd.Amount,
            allocatedAmount: cmd.AllocatedAmount,
            consumedAmount: cmd.ConsumedAmount,
            availableAmount: cmd.AvailableAmount,
            currency: cmd.Currency,
            merchantLabel: cmd.MerchantLabel,
            recordedAt: cmd.RecordedAt,
            now: _clock.GetUtcNow().UtcDateTime);
    }
}
