using System.Text.Json.Serialization;

namespace Reliever.BeneficiaryDashboard.Bff.Contracts.UpstreamEvents;

/// <summary>
/// Wire shape of RVT.BSP.004.CONSUMPTION_RECORDED. The authoritative
/// shape lives in
/// process/CAP.BSP.004.ENV/schemas/RVT.BSP.004.CONSUMPTION_RECORDED.schema.json.
///
/// Note: 'allocated_amount' is NOT carried by the upstream schema today.
/// The dashboard derives it as consumed_amount_after + remaining_amount
/// in the consumer (see README assumption A5).
/// </summary>
public sealed record EnvelopeConsumptionRecordedPayload(
    [property: JsonPropertyName("event_id")] string EventId,
    [property: JsonPropertyName("occurred_at")] DateTime OccurredAt,
    [property: JsonPropertyName("case_id")] string CaseId,
    [property: JsonPropertyName("period_index")] int PeriodIndex,
    [property: JsonPropertyName("allocation_id")] string AllocationId,
    [property: JsonPropertyName("category")] string Category,
    [property: JsonPropertyName("amount")] decimal Amount,
    [property: JsonPropertyName("consumed_amount_after")] decimal ConsumedAmountAfter,
    [property: JsonPropertyName("remaining_amount")] decimal RemainingAmount,
    [property: JsonPropertyName("transaction_id")] string? TransactionId,
    [property: JsonPropertyName("causation_event_id")] string? CausationEventId);
