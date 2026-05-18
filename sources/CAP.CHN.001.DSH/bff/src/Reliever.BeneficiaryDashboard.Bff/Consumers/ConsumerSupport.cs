using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using MassTransit;

namespace Reliever.BeneficiaryDashboard.Bff.Consumers;

/// <summary>
/// Helpers shared by the three RVT consumers. Upstream producers
/// (CAP.BSP.001.SCO / .TIE / .ENV) publish RAW JSON payloads on their
/// topic exchanges — no MassTransit envelope. We read the raw body
/// via the <see cref="MessageBody"/> payload, run the upstream JSON
/// Schema validator + PII scanner, then deserialise into a typed
/// record. Throwing on validation failure surfaces to the DLQ via
/// MassTransit's <c>_error</c> queue convention.
/// </summary>
internal static class ConsumerSupport
{
    private static readonly JsonSerializerOptions JsonOpts = new(JsonSerializerDefaults.Web);

    public static (JsonNode parsed, string raw) ReadRawJson(ConsumeContext context)
    {
        if (!context.TryGetPayload<MessageBody>(out var body))
        {
            throw new InvalidOperationException(
                "Could not read raw message body — the receive endpoint is not configured for raw JSON.");
        }

        var bytes = body!.GetBytes();
        var rawText = Encoding.UTF8.GetString(bytes.ToArray());
        var parsed = JsonNode.Parse(rawText)
                     ?? throw new InvalidOperationException("Payload is empty or null JSON.");
        return (parsed, rawText);
    }

    public static T Deserialize<T>(string raw)
    {
        return JsonSerializer.Deserialize<T>(raw, JsonOpts)
               ?? throw new InvalidOperationException(
                   $"Failed to deserialise raw JSON into {typeof(T).Name}.");
    }
}
