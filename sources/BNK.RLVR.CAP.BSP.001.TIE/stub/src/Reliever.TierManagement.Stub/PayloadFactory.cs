using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Reliever.TierManagement.Stub;

/// <summary>
/// Generates simulated upward tier-crossing payloads honoring the runtime contract
/// (BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED — domain event DDD form).
///
/// Each simulated case progresses through the configured tier sequence
/// (e.g. T0 → T1 → T2 → T3). The last hop sets est_sortie_programme=true.
/// direction is constrained to "UPGRADE" (upward only — Epic 1 scope).
/// </summary>
public sealed class PayloadFactory
{
    private readonly StubOptions _options;
    private readonly ILogger<PayloadFactory> _logger;
    private readonly Random _random;

    /// <summary>
    /// Per-case progression cursor — index in StubOptions.TierProgression.
    /// At each emission, the cursor advances; once it reaches the last tier
    /// (programme exit), it wraps around to position 0 (representing a fresh case).
    /// </summary>
    private readonly Dictionary<string, int> _caseCursors = new();

    public static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = null,
        WriteIndented = false,
        DefaultIgnoreCondition = JsonIgnoreCondition.Never,
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
    };

    public PayloadFactory(IOptions<StubOptions> options, ILogger<PayloadFactory> logger)
    {
        _options = options.Value;
        _logger = logger;
        _random = new Random();

        if (_options.TierProgression.Count < 2)
        {
            throw new InvalidOperationException(
                "TierProgression must contain at least 2 tier codes to simulate an upward crossing.");
        }
        if (_options.CaseIds.Count == 0)
        {
            throw new InvalidOperationException(
                "CaseIds must contain at least one simulated case_id.");
        }

        // Initialise each case at tier 0 (lowest of the progression).
        foreach (var caseId in _options.CaseIds)
        {
            _caseCursors[caseId] = 0;
        }
    }

    /// <summary>
    /// Builds the next simulated payload as a JSON string, advancing the case cursor.
    /// Round-robins across configured cases.
    /// </summary>
    public (string PayloadJson, string CaseId) BuildNext(int rotationIndex)
    {
        var caseId = _options.CaseIds[rotationIndex % _options.CaseIds.Count];
        var cursor = _caseCursors[caseId];

        // If the case already reached the last tier, rotate it back to zero —
        // simulates a fresh case starting over.
        if (cursor >= _options.TierProgression.Count - 1)
        {
            cursor = 0;
            _caseCursors[caseId] = 0;
        }

        var previousTier = _options.TierProgression[cursor];
        var newTier = _options.TierProgression[cursor + 1];
        _caseCursors[caseId] = cursor + 1;

        var estSortieProgramme = (cursor + 1) == _options.TierProgression.Count - 1;

        // Trigger source: ~80% algorithmic, ~20% prescriber override (realistic mix).
        var trigger = _random.NextDouble() < 0.80 ? "ALGORITHM" : "PRESCRIBER_OVERRIDE";

        // Score in a realistic range — higher for higher tier transitions.
        var score = Math.Round(50.0 + (cursor * 12.5) + (_random.NextDouble() * 5), 2);

        var payload = new TierUpgradeRecordedPayload
        {
            transition_id = $"TRX-{Guid.NewGuid():N}",
            case_id = caseId,
            previous_tier = previousTier,
            new_tier = newTier,
            direction = "UPGRADE", // Constrained — upward only (Epic 1 scope).
            trigger = trigger,
            score_at_time = score,
            transition_timestamp = DateTimeOffset.UtcNow.ToString("O"),
            est_sortie_programme = estSortieProgramme
        };

        var json = JsonSerializer.Serialize(payload, JsonOptions);
        _logger.LogDebug(
            "Built payload: case={CaseId} {Prev}→{Next} trigger={Trigger} sortie={Exit}",
            caseId, previousTier, newTier, trigger, estSortieProgramme);

        return (json, caseId);
    }

    /// <summary>
    /// Domain event DDD payload mirroring the runtime schema.
    /// Property names are snake_case to match the contract — no JsonPropertyName decoration needed
    /// because the property names already match the wire format.
    /// </summary>
    private sealed class TierUpgradeRecordedPayload
    {
        public string transition_id { get; set; } = "";
        public string case_id { get; set; } = "";
        public string previous_tier { get; set; } = "";
        public string new_tier { get; set; } = "";
        public string direction { get; set; } = "";
        public string trigger { get; set; } = "";
        public double score_at_time { get; set; }
        public string transition_timestamp { get; set; } = "";
        public bool est_sortie_programme { get; set; }
    }
}
