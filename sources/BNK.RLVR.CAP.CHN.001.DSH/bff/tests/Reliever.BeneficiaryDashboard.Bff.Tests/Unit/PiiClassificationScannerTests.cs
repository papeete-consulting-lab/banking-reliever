using System.Text.Json.Nodes;
using FluentAssertions;
using Reliever.BeneficiaryDashboard.Bff.Domain.Validators;
using Xunit;

namespace Reliever.BeneficiaryDashboard.Bff.Tests.Unit;

public class PiiClassificationScannerTests
{
    [Fact]
    public void CleanPayload_IsAllowed()
    {
        var payload = JsonNode.Parse("""
            {
              "case_id": "00000000-0000-7000-8000-000000000001",
              "score_value": 42.5,
              "delta_score": 2.5,
              "computation_timestamp": "2026-05-16T10:00:00Z",
              "trigger": { "kind": "TRANSACTION_AUTHORIZED", "event_id": "abc", "polarity": "positive" }
            }
            """);

        PiiClassificationScanner.IsPiiFree(payload, out var path).Should().BeTrue();
        path.Should().BeNull();
    }

    [Theory]
    [InlineData("first_name", "Marie")]
    [InlineData("email", "marie@example.com")]
    [InlineData("phone_number", "+33611223344")]
    [InlineData("merchant_name", "Carrefour")]
    [InlineData("internal_id", "ben-42")]
    public void DenyListed_TopLevelField_IsRejected(string field, string value)
    {
        var payload = JsonNode.Parse($$"""
            {
              "case_id": "00000000-0000-7000-8000-000000000001",
              "{{field}}": "{{value}}"
            }
            """);

        var ok = PiiClassificationScanner.IsPiiFree(payload, out var path);

        ok.Should().BeFalse();
        path.Should().Be($"$.{field}");
    }

    [Fact]
    public void DenyListed_NestedField_IsRejected()
    {
        var payload = JsonNode.Parse("""
            {
              "case_id": "00000000-0000-7000-8000-000000000001",
              "trigger": {
                "kind": "TRANSACTION_AUTHORIZED",
                "event_id": "abc",
                "contact_details": { "email": "leaks@example.com" }
              }
            }
            """);

        var ok = PiiClassificationScanner.IsPiiFree(payload, out var path);

        ok.Should().BeFalse();
        path.Should().StartWith("$.trigger.contact_details");
    }
}
