using System.Text.Json.Serialization;

namespace Reliever.BeneficiaryDashboard.Bff.Contracts.UpstreamEvents;

/// <summary>
/// Wire shape of RVT.BSP.001.CURRENT_SCORE_RECOMPUTED, narrowed to the
/// fields the dashboard actually needs (case_id, envelope.message_id,
/// score_value, delta_score, computation_timestamp, trigger.event_id,
/// model_version).
///
/// The authoritative shape lives in
/// process/CAP.BSP.001.SCO/schemas/RVT.BSP.001.CURRENT_SCORE_RECOMPUTED.schema.json
/// — the consumer validates the raw JSON against that schema BEFORE
/// deserialising into this type (defence-in-depth: deserialisation
/// would also reject malformed payloads, but explicit schema validation
/// surfaces structured DLQ reasons).
///
/// PII: this payload type intentionally excludes nested objects that
/// could carry PII. The full upstream payload is still scanned by
/// PiiClassificationScanner before reaching this DTO.
/// </summary>
public sealed record ScoreRecomputedPayload(
    [property: JsonPropertyName("envelope")] ScoreEnvelopeMeta Envelope,
    [property: JsonPropertyName("case_id")] string CaseId,
    [property: JsonPropertyName("score_value")] decimal ScoreValue,
    [property: JsonPropertyName("delta_score")] decimal DeltaScore,
    [property: JsonPropertyName("model_version")] string ModelVersion,
    [property: JsonPropertyName("computation_timestamp")] DateTime ComputationTimestamp,
    [property: JsonPropertyName("trigger")] ScoreTriggerMeta Trigger);

public sealed record ScoreEnvelopeMeta(
    [property: JsonPropertyName("message_id")] string MessageId,
    [property: JsonPropertyName("emitted_at")] DateTime EmittedAt,
    [property: JsonPropertyName("emitting_capability")] string EmittingCapability,
    [property: JsonPropertyName("correlation_id")] string CorrelationId,
    [property: JsonPropertyName("causation_id")] string CausationId);

public sealed record ScoreTriggerMeta(
    [property: JsonPropertyName("kind")] string Kind,
    [property: JsonPropertyName("event_id")] string EventId,
    [property: JsonPropertyName("polarity")] string Polarity);
