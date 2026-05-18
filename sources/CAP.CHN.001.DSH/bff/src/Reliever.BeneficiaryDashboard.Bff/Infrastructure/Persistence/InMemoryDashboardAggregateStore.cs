using System.Collections.Concurrent;
using Microsoft.Extensions.Options;
using Reliever.BeneficiaryDashboard.Bff.Domain;

namespace Reliever.BeneficiaryDashboard.Bff.Infrastructure.Persistence;

/// <summary>
/// Thread-safe in-memory store of BeneficiaryDashboard aggregates.
/// Backed by <see cref="ConcurrentDictionary{TKey,TValue}"/> using
/// case_id as the key. The aggregate itself owns its own write lock —
/// the store only needs to serialise create-vs-create races.
/// </summary>
public sealed class InMemoryDashboardAggregateStore : IDashboardAggregateStore
{
    private readonly ConcurrentDictionary<string, Domain.BeneficiaryDashboard> _byCaseId = new(StringComparer.Ordinal);
    private readonly AggregateOptions _options;

    public InMemoryDashboardAggregateStore(IOptions<AggregateOptions> options)
    {
        _options = options.Value;
    }

    public Domain.BeneficiaryDashboard GetOrCreate(string caseId)
        => _byCaseId.GetOrAdd(caseId, id => new Domain.BeneficiaryDashboard(id, _options));

    public bool TryGet(string caseId, out Domain.BeneficiaryDashboard? aggregate)
    {
        var found = _byCaseId.TryGetValue(caseId, out var agg);
        aggregate = agg;
        return found;
    }

    public int Count => _byCaseId.Count;
}
