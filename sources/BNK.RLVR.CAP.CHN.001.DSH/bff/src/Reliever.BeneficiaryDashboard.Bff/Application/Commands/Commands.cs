namespace Reliever.BeneficiaryDashboard.Bff.Application.Commands;

/// <summary>
/// CMD.CHN.001.DSH.SYNCHRONIZE_SCORE — issued by POL.ON_SCORE_RECOMPUTED.
/// Internal — never crosses the wire.
/// </summary>
public sealed record SynchronizeScoreCommand(
    string CaseId,
    string EventId,
    decimal ScoreValue,
    decimal? DeltaScore,
    DateTime RecomputedAt,
    string? ModelVersion);

/// <summary>
/// CMD.CHN.001.DSH.SYNCHRONIZE_TIER — issued by POL.ON_TIER_UPGRADE_RECORDED.
/// Internal — never crosses the wire.
/// </summary>
public sealed record SynchronizeTierCommand(
    string CaseId,
    string EventId,
    string? PreviousTierCode,
    string CurrentTierCode,
    DateTime UpgradedAt);

/// <summary>
/// CMD.CHN.001.DSH.RECORD_ENVELOPE_CONSUMPTION — issued by
/// POL.ON_ENVELOPE_CONSUMPTION_RECORDED. Internal — never crosses the wire.
/// </summary>
public sealed record RecordEnvelopeConsumptionCommand(
    string CaseId,
    string EventId,
    string EnvelopeId,
    string Category,
    string TransactionId,
    decimal Amount,
    string Currency,
    string? MerchantLabel,
    decimal AllocatedAmount,
    decimal ConsumedAmount,
    decimal AvailableAmount,
    DateTime RecordedAt);
