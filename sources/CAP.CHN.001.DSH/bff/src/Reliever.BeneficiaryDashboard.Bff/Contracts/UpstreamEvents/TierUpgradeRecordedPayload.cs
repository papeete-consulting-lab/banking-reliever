using System.Text.Json.Serialization;

namespace Reliever.BeneficiaryDashboard.Bff.Contracts.UpstreamEvents;

/// <summary>
/// Wire shape of RVT.BSP.001.TIER_UPGRADE_RECORDED. The authoritative
/// shape lives in
/// process/CAP.BSP.001.TIE/schemas/RVT.BSP.001.TIER_UPGRADE_RECORDED.schema.json.
/// </summary>
public sealed record TierUpgradeRecordedPayload(
    [property: JsonPropertyName("event_id")] string EventId,
    [property: JsonPropertyName("case_id")] string CaseId,
    [property: JsonPropertyName("transition")] TierTransitionMeta Transition,
    [property: JsonPropertyName("occurred_at")] DateTime OccurredAt);

public sealed record TierTransitionMeta(
    [property: JsonPropertyName("from_tier_code")] string FromTierCode,
    [property: JsonPropertyName("to_tier_code")] string ToTierCode,
    [property: JsonPropertyName("cause")] string Cause,
    [property: JsonPropertyName("tier_definitions_version")] string TierDefinitionsVersion);
