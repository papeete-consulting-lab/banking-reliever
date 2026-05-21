namespace Reliever.BeneficiaryDashboard.Bff.Domain;

/// <summary>
/// Open envelope snapshot held by AGG.BENEFICIARY_DASHBOARD.open_envelopes.
/// PII-free per INV.DSH.001 — only semantic labels and amounts.
/// </summary>
public sealed record EnvelopeSnapshot(
    string EnvelopeId,
    string Category,
    decimal AllocatedAmount,
    decimal ConsumedAmount,
    decimal AvailableAmount,
    string Currency,
    DateTime LastUpdatedAt);

/// <summary>
/// Recent-transactions feed entry held by AGG.BENEFICIARY_DASHBOARD.recent_transactions.
/// Bounded by INV.DSH.005 (50 entries / 30d, FIFO on RecordedAt).
/// merchant_label is a non-PII semantic label (e.g. "GROCERY") derived
/// upstream by CAP.BSP.004.ENV — never a raw merchant name.
/// </summary>
public sealed record TransactionEntry(
    string TransactionId,
    string EnvelopeId,
    string Category,
    decimal Amount,
    string Currency,
    string? MerchantLabel,
    DateTime RecordedAt);
