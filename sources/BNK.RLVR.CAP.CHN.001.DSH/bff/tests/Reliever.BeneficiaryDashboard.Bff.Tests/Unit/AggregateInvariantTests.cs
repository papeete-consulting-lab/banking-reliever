using FluentAssertions;
using Reliever.BeneficiaryDashboard.Bff.Domain;
using Xunit;

namespace Reliever.BeneficiaryDashboard.Bff.Tests.Unit;

public class AggregateInvariantTests
{
    private static AggregateOptions DefaultOptions() => new()
    {
        ProcessedEventIdsBound = 200,
        ProcessedEventIdsAgeDays = 30,
        RecentTransactionsBound = 50,
        RecentTransactionsAgeDays = 30,
        SnapshotEveryNEvents = 100,
    };

    [Fact]
    public void InvDsh006_LazyMaterialisationViaScore_PopulatesOnlyScoreFields()
    {
        var agg = new Domain.BeneficiaryDashboard("case-1", DefaultOptions());
        var now = DateTime.UtcNow;

        var outcome = agg.ApplySynchronizeScore("evt-1", 42.5m, now, now);

        outcome.Should().Be(CommandOutcome.Applied);
        var view = agg.GetView();
        view.CurrentScore.Should().Be(42.5m);
        view.ScoreRecomputedAt.Should().Be(now);
        view.CurrentTierCode.Should().BeNull();      // not touched by score
        view.OpenEnvelopes.Should().BeEmpty();       // not touched by score
    }

    [Fact]
    public void InvDsh002_DuplicateEventIdIsAckAndDrop()
    {
        var agg = new Domain.BeneficiaryDashboard("case-1", DefaultOptions());
        var t = DateTime.UtcNow;

        var first  = agg.ApplySynchronizeScore("evt-1", 10m, t, t);
        var second = agg.ApplySynchronizeScore("evt-1", 99m, t.AddMinutes(1), t.AddMinutes(1));

        first.Should().Be(CommandOutcome.Applied);
        second.Should().Be(CommandOutcome.EventAlreadyProcessed);
        agg.GetView().CurrentScore.Should().Be(10m, "the second application must be a no-op");
    }

    [Fact]
    public void InvDsh003_StaleScoreIsAckAndDrop()
    {
        var agg = new Domain.BeneficiaryDashboard("case-1", DefaultOptions());
        var t0 = DateTime.UtcNow;
        var t1 = t0.AddSeconds(10);

        agg.ApplySynchronizeScore("evt-1", 10m, t1, t1);
        var stale = agg.ApplySynchronizeScore("evt-2", 5m, t0, t1.AddSeconds(1));

        stale.Should().Be(CommandOutcome.StaleEvent);
        agg.GetView().CurrentScore.Should().Be(10m);
        agg.GetView().ScoreRecomputedAt.Should().Be(t1);
    }

    [Fact]
    public void InvDsh003_StaleTierIsAckAndDrop()
    {
        var agg = new Domain.BeneficiaryDashboard("case-1", DefaultOptions());
        var t0 = DateTime.UtcNow;
        var t1 = t0.AddSeconds(10);

        agg.ApplySynchronizeTier("evt-1", "T2", t1, t1);
        var stale = agg.ApplySynchronizeTier("evt-2", "T1", t0, t1.AddSeconds(1));

        stale.Should().Be(CommandOutcome.StaleEvent);
        agg.GetView().CurrentTierCode.Should().Be("T2");
    }

    [Fact]
    public void InvDsh005_RecentTransactions_BoundedAt50_FifoEvictionByRecordedAt()
    {
        var agg = new Domain.BeneficiaryDashboard("case-1", DefaultOptions());
        var t0 = DateTime.UtcNow.AddDays(-5); // all within 30d window

        for (var i = 0; i < 100; i++)
        {
            agg.ApplyRecordEnvelopeConsumption(
                eventId: $"evt-{i}",
                envelopeId: "env-1",
                transactionId: $"tx-{i}",
                category: "GROCERY",
                amount: 1m,
                allocatedAmount: 100m,
                consumedAmount: i + 1m,
                availableAmount: 99m - i,
                currency: "EUR",
                merchantLabel: null,
                recordedAt: t0.AddMinutes(i),
                now: DateTime.UtcNow);
        }

        var feed = agg.GetRecentTransactions();
        feed.Count.Should().Be(50, "INV.DSH.005 caps recent_transactions at 50 entries");
        // Most-recent-first.
        feed.First().RecordedAt.Should().BeAfter(feed.Last().RecordedAt);
        // The oldest entry should be at least 50 ticks newer than the original first.
        feed.Last().TransactionId.Should().Be("tx-50");
    }

    [Fact]
    public void InvDsh005_RecentTransactions_AgeEvictionPast30Days()
    {
        var agg = new Domain.BeneficiaryDashboard("case-1", DefaultOptions());
        var now = DateTime.UtcNow;

        // 5 ancient entries (40 days old) + 5 fresh entries (5 days old)
        for (var i = 0; i < 5; i++)
        {
            agg.ApplyRecordEnvelopeConsumption(
                eventId: $"old-{i}",
                envelopeId: "env-1", transactionId: $"old-tx-{i}",
                category: "GROCERY", amount: 1m,
                allocatedAmount: 100m, consumedAmount: i, availableAmount: 100m - i,
                currency: "EUR", merchantLabel: null,
                recordedAt: now.AddDays(-40 - i),
                now: now);
        }
        for (var i = 0; i < 5; i++)
        {
            agg.ApplyRecordEnvelopeConsumption(
                eventId: $"new-{i}",
                envelopeId: "env-1", transactionId: $"new-tx-{i}",
                category: "GROCERY", amount: 2m,
                allocatedAmount: 100m, consumedAmount: 5 + i, availableAmount: 95m - i,
                currency: "EUR", merchantLabel: null,
                recordedAt: now.AddDays(-i),
                now: now);
        }

        var feed = agg.GetRecentTransactions();
        feed.Should().OnlyContain(t => t.TransactionId.StartsWith("new-tx-"),
            "30d-old entries are evicted on write-time");
        feed.Count.Should().Be(5);
    }

    [Fact]
    public void EtagAdvancesOnEveryAcceptedMutation_AndIsStableUntilNextMutation()
    {
        var agg = new Domain.BeneficiaryDashboard("case-1", DefaultOptions());
        var t = DateTime.UtcNow;

        var etag0 = agg.ETag;
        agg.ApplySynchronizeScore("evt-1", 10m, t, t);
        var etag1 = agg.ETag;

        etag1.Should().NotBe(etag0);

        // No mutation between two reads -> identical ETag (deterministic from state)
        agg.ETag.Should().Be(etag1);

        // Idempotent replay -> ETag unchanged
        agg.ApplySynchronizeScore("evt-1", 10m, t, t.AddMilliseconds(1));
        agg.ETag.Should().Be(etag1);

        // Genuine mutation -> ETag advances
        agg.ApplySynchronizeScore("evt-2", 11m, t.AddSeconds(1), t.AddSeconds(1));
        agg.ETag.Should().NotBe(etag1);
    }

    [Fact]
    public void EtagIsDeterministicForEquivalentState()
    {
        var a = new Domain.BeneficiaryDashboard("case-1", DefaultOptions());
        var b = new Domain.BeneficiaryDashboard("case-1", DefaultOptions());
        var t = DateTime.SpecifyKind(new DateTime(2026, 5, 16, 10, 0, 0), DateTimeKind.Utc);

        a.ApplySynchronizeScore("evt-1", 7m, t, t);
        a.ApplySynchronizeTier("evt-2", "T2", t.AddSeconds(1), t.AddSeconds(1));

        b.ApplySynchronizeTier("evt-2", "T2", t.AddSeconds(1), t.AddSeconds(1));
        b.ApplySynchronizeScore("evt-1", 7m, t, t);

        a.ETag.Should().Be(b.ETag,
            "ETag is a pure function of state — application order must not influence it");
    }
}
