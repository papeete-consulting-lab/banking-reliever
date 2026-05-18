using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using Json.Schema;

namespace Reliever.BeneficiaryDashboard.Bff.Domain.Validators;

/// <summary>
/// Loads each upstream RVT JSON Schema once at startup (fail-fast if any
/// schema file is missing) and exposes deterministic validation per
/// upstream-channel name.
///
/// Schemas live under process/CAP.BSP.*/schemas/ — read-only contracts
/// owned by the producer capabilities. They are copied into the build
/// output by the .csproj (Link="process-schemas/...").
///
/// Validation failure semantics:
///   * Schema-shape error  → caller routes to DLQ via MassTransit's
///                            built-in <c>_error</c> queue convention
///                            (the consumer throws).
///   * PII-classification  → see PiiClassificationScanner. The scanner
///                            does NOT consult the upstream schema's
///                            "pii_classification" annotation (none are
///                            declared in process/CAP.BSP.*/schemas/ as
///                            of v0.2.0); instead it enforces INV.DSH.001
///                            by allowlisting known non-PII property
///                            paths per channel.
/// </summary>
public sealed class UpstreamSchemaValidator
{
    private readonly JsonSchema _scoreSchema;
    private readonly JsonSchema _tierSchema;
    private readonly JsonSchema _envelopeSchema;

    public UpstreamSchemaValidator(string contentRoot)
    {
        var scoreSchemaPath = Path.Combine(
            contentRoot, "process-schemas", "bsp.001.sco",
            "RVT.BSP.001.CURRENT_SCORE_RECOMPUTED.schema.json");
        var tierSchemaPath = Path.Combine(
            contentRoot, "process-schemas", "bsp.001.tie",
            "RVT.BSP.001.TIER_UPGRADE_RECORDED.schema.json");
        var envelopeSchemaPath = Path.Combine(
            contentRoot, "process-schemas", "bsp.004.env",
            "RVT.BSP.004.CONSUMPTION_RECORDED.schema.json");

        _scoreSchema = LoadOrThrow(scoreSchemaPath, "RVT.BSP.001.CURRENT_SCORE_RECOMPUTED");
        _tierSchema = LoadOrThrow(tierSchemaPath, "RVT.BSP.001.TIER_UPGRADE_RECORDED");
        _envelopeSchema = LoadOrThrow(envelopeSchemaPath, "RVT.BSP.004.CONSUMPTION_RECORDED");
    }

    public bool ValidateScore(JsonNode payload, out string? error)
        => Validate(_scoreSchema, payload, out error);

    public bool ValidateTier(JsonNode payload, out string? error)
        => Validate(_tierSchema, payload, out error);

    public bool ValidateEnvelopeConsumption(JsonNode payload, out string? error)
        => Validate(_envelopeSchema, payload, out error);

    private static bool Validate(JsonSchema schema, JsonNode payload, out string? error)
    {
        var result = schema.Evaluate(payload, new EvaluationOptions
        {
            OutputFormat = OutputFormat.List,
        });

        if (result.IsValid)
        {
            error = null;
            return true;
        }

        // Compact one-line summary of the first few failures (for DLQ
        // diagnostics — full report would explode the message header size).
        var details = result.Details
            .Where(d => d.HasErrors)
            .SelectMany(d => d.Errors!.Select(e => $"{d.InstanceLocation}: {e.Value}"))
            .Take(5);
        error = string.Join("; ", details);
        return false;
    }

    private static JsonSchema LoadOrThrow(string path, string label)
    {
        if (!File.Exists(path))
        {
            throw new FileNotFoundException(
                $"Upstream schema for {label} not found at {path}. " +
                "The .csproj must copy process/CAP.BSP.*/schemas/ into the build output.");
        }

        try
        {
            return JsonSchema.FromFile(path);
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException(
                $"Failed to parse upstream schema for {label} at {path}: {ex.Message}", ex);
        }
    }
}
