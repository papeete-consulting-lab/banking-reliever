namespace Reliever.BeneficiaryDashboard.Bff.Domain;

/// <summary>
/// Configuration knobs for the BeneficiaryDashboard aggregate.
/// Bound from configuration section "Aggregate" — defaults match
/// process/CAP.CHN.001.DSH/aggregates.yaml.
/// </summary>
public sealed class AggregateOptions
{
    public int ProcessedEventIdsBound { get; set; } = 200;
    public int ProcessedEventIdsAgeDays { get; set; } = 30;
    public int RecentTransactionsBound { get; set; } = 50;
    public int RecentTransactionsAgeDays { get; set; } = 30;
    public int SnapshotEveryNEvents { get; set; } = 100;
}
