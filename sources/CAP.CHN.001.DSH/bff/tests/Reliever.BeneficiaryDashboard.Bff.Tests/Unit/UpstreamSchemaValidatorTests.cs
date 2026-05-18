using System.IO;
using System.Text.Json.Nodes;
using FluentAssertions;
using Reliever.BeneficiaryDashboard.Bff.Domain.Validators;
using Xunit;

namespace Reliever.BeneficiaryDashboard.Bff.Tests.Unit;

/// <summary>
/// Resolves the build-output process-schemas directory and exercises the
/// validator against minimal valid + invalid payloads. The .csproj copies
/// process/CAP.BSP.*/schemas/ into the test bin folder via the project
/// reference's Content items.
/// </summary>
public class UpstreamSchemaValidatorTests
{
    private static UpstreamSchemaValidator BuildValidator()
        => new(AppContext.BaseDirectory);

    [Fact]
    public void ValidScoreRecomputedPayload_PassesValidation()
    {
        var payload = JsonNode.Parse("""
            {
              "envelope": {
                "message_id": "00000000-0000-7000-8000-000000000001",
                "schema_version": "0.1.0",
                "emitted_at": "2026-05-16T10:00:00Z",
                "emitting_capability": "CAP.BSP.001.SCO",
                "correlation_id": "00000000-0000-7000-8000-000000000002",
                "causation_id": "00000000-0000-7000-8000-000000000003"
              },
              "case_id": "00000000-0000-7000-8000-000000000002",
              "evaluation_id": "00000000-0000-7000-8000-000000000004",
              "score_value": 42.5,
              "delta_score": 2.5,
              "model_version": "1.0.0",
              "evaluation_type": "CURRENT",
              "computation_timestamp": "2026-05-16T10:00:00Z",
              "trigger": {
                "kind": "TRANSACTION_AUTHORIZED",
                "event_id": "00000000-0000-7000-8000-000000000003",
                "polarity": "positive"
              },
              "contributing_factors": []
            }
            """)!;

        var ok = BuildValidator().ValidateScore(payload, out var error);
        ok.Should().BeTrue(error);
    }

    [Fact]
    public void InvalidScoreRecomputedPayload_FailsValidation()
    {
        // Missing required 'envelope' object.
        var payload = JsonNode.Parse("""
            { "case_id": "x", "score_value": "not-a-number" }
            """)!;

        var ok = BuildValidator().ValidateScore(payload, out var error);
        ok.Should().BeFalse();
        error.Should().NotBeNullOrEmpty();
    }

    [Fact]
    public void ValidTierUpgradeRecordedPayload_PassesValidation()
    {
        var payload = JsonNode.Parse("""
            {
              "event_id": "11111111-1111-7111-8111-111111111111",
              "case_id": "case-42",
              "transition": {
                "from_tier_code": "T1",
                "to_tier_code": "T2",
                "cause": "SCORE_THRESHOLD",
                "tier_definitions_version": "v1"
              },
              "occurred_at": "2026-05-16T10:00:00Z"
            }
            """)!;

        var ok = BuildValidator().ValidateTier(payload, out var error);
        ok.Should().BeTrue(error);
    }

    [Fact]
    public void ValidConsumptionRecordedPayload_PassesValidation()
    {
        var payload = JsonNode.Parse("""
            {
              "event_id": "22222222-2222-7222-8222-222222222222",
              "occurred_at": "2026-05-16T10:00:00Z",
              "case_id": "case-42",
              "period_index": 0,
              "allocation_id": "env-1",
              "category": "GROCERY",
              "amount": 12.50,
              "consumed_amount_after": 12.50,
              "remaining_amount": 87.50
            }
            """)!;

        var ok = BuildValidator().ValidateEnvelopeConsumption(payload, out var error);
        ok.Should().BeTrue(error);
    }

    [Fact]
    public void Constructor_ThrowsIfSchemaFileMissing()
    {
        var nonExistent = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"));
        Action act = () => new UpstreamSchemaValidator(nonExistent);
        act.Should().Throw<FileNotFoundException>();
    }
}
