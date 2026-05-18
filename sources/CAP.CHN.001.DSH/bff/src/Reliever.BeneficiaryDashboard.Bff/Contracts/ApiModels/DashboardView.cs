using System.Text.Json.Serialization;

namespace Reliever.BeneficiaryDashboard.Bff.Contracts.ApiModels;

/// <summary>
/// Wire shape served by GET /capabilities/chn/001/dsh/cases/{case_id}/dashboard.
/// Mirrors PRJ.CHN.001.DSH.DASHBOARD_VIEW from
/// process/CAP.CHN.001.DSH/read-models.yaml.
///
/// All fields are nullable until populated by the corresponding policy
/// (lazy materialisation — INV.DSH.006). The frontend renders an
/// empty-state placeholder when these are null (per TASK-002).
/// </summary>
public sealed record DashboardView(
    [property: JsonPropertyName("case_id")] string CaseId,
    [property: JsonPropertyName("current_tier_code")] string? CurrentTierCode,
    [property: JsonPropertyName("tier_upgraded_at")] DateTime? TierUpgradedAt,
    [property: JsonPropertyName("current_score")] decimal? CurrentScore,
    [property: JsonPropertyName("score_recomputed_at")] DateTime? ScoreRecomputedAt,
    [property: JsonPropertyName("open_envelopes")] IReadOnlyList<DashboardEnvelopeView> OpenEnvelopes,
    [property: JsonPropertyName("last_synced_at")] DateTime? LastSyncedAt);

public sealed record DashboardEnvelopeView(
    [property: JsonPropertyName("envelope_id")] string EnvelopeId,
    [property: JsonPropertyName("category")] string Category,
    [property: JsonPropertyName("allocated_amount")] decimal AllocatedAmount,
    [property: JsonPropertyName("consumed_amount")] decimal ConsumedAmount,
    [property: JsonPropertyName("available_amount")] decimal AvailableAmount,
    [property: JsonPropertyName("currency")] string Currency,
    [property: JsonPropertyName("last_updated_at")] DateTime LastUpdatedAt);

public sealed record RecentTransactionView(
    [property: JsonPropertyName("transaction_id")] string TransactionId,
    [property: JsonPropertyName("envelope_id")] string EnvelopeId,
    [property: JsonPropertyName("category")] string Category,
    [property: JsonPropertyName("amount")] decimal Amount,
    [property: JsonPropertyName("currency")] string Currency,
    [property: JsonPropertyName("merchant_label")] string? MerchantLabel,
    [property: JsonPropertyName("recorded_at")] DateTime RecordedAt);
