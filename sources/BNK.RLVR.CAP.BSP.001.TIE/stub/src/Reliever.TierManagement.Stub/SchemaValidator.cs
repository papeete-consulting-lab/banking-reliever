using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using NJsonSchema;
using NJsonSchema.Validation;

namespace Reliever.TierManagement.Stub;

/// <summary>
/// Loads the runtime JSON Schema for BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED at startup
/// and validates every outgoing payload against it. Fail-fast on schema violations.
///
/// Per Definition of Done: every payload published by the stub MUST validate against
/// the runtime schema (automated check at the publish site).
/// </summary>
public sealed class SchemaValidator
{
    private readonly JsonSchema _schema;
    private readonly ILogger<SchemaValidator> _logger;

    public SchemaValidator(IOptions<StubOptions> options, ILogger<SchemaValidator> logger)
    {
        _logger = logger;
        var schemaPath = ResolveSchemaPath(options.Value.Schema.RuntimeSchemaPath);

        if (!File.Exists(schemaPath))
        {
            throw new FileNotFoundException(
                $"Runtime JSON Schema not found at '{schemaPath}'. " +
                "The stub cannot start without the contract — fail-fast per Mode B requirements.",
                schemaPath);
        }

        var schemaJson = File.ReadAllText(schemaPath);
        _schema = JsonSchema.FromJsonAsync(schemaJson).GetAwaiter().GetResult();
        var bcmVersion = (_schema.ExtensionData != null && _schema.ExtensionData.TryGetValue("x-bcm-version", out var v))
            ? v?.ToString() ?? "unknown"
            : "unknown";
        _logger.LogInformation(
            "Loaded runtime JSON Schema for BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED from '{Path}' (x-bcm-version={Version}).",
            schemaPath,
            bcmVersion);
    }

    /// <summary>
    /// Validates the JSON payload against the runtime schema.
    /// Throws SchemaValidationException with the list of violations if any.
    /// </summary>
    public void Validate(string payloadJson)
    {
        var errors = _schema.Validate(payloadJson);
        if (errors.Count > 0)
        {
            var errorList = string.Join("; ", errors.Select(FormatError));
            throw new SchemaValidationException(
                $"Payload does not validate against BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED schema: {errorList}",
                errors);
        }
    }

    private static string FormatError(ValidationError error)
        => $"{error.Path} → {error.Kind} ({error.Property})";

    private static string ResolveSchemaPath(string configuredPath)
    {
        if (Path.IsPathRooted(configuredPath))
        {
            return configuredPath;
        }
        return Path.Combine(AppContext.BaseDirectory, configuredPath);
    }
}

public sealed class SchemaValidationException : Exception
{
    public ICollection<ValidationError> Errors { get; }

    public SchemaValidationException(string message, ICollection<ValidationError> errors) : base(message)
    {
        Errors = errors;
    }
}
