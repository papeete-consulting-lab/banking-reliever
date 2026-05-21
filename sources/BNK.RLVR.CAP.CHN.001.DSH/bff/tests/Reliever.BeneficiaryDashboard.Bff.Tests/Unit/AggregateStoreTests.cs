using FluentAssertions;
using Microsoft.Extensions.Options;
using Reliever.BeneficiaryDashboard.Bff.Domain;
using Reliever.BeneficiaryDashboard.Bff.Infrastructure.Persistence;
using Xunit;

namespace Reliever.BeneficiaryDashboard.Bff.Tests.Unit;

public class AggregateStoreTests
{
    [Fact]
    public void GetOrCreate_IsIdempotentForTheSameCaseId()
    {
        var store = new InMemoryDashboardAggregateStore(
            Options.Create(new AggregateOptions()));

        var a = store.GetOrCreate("case-1");
        var b = store.GetOrCreate("case-1");

        a.Should().BeSameAs(b, "INV.DSH.006 — one aggregate per case_id");
        store.Count.Should().Be(1);
    }

    [Fact]
    public void TryGet_ReturnsFalseUntilMaterialised()
    {
        var store = new InMemoryDashboardAggregateStore(
            Options.Create(new AggregateOptions()));

        store.TryGet("case-1", out var before).Should().BeFalse();
        before.Should().BeNull();

        store.GetOrCreate("case-1");

        store.TryGet("case-1", out var after).Should().BeTrue();
        after.Should().NotBeNull();
    }
}
