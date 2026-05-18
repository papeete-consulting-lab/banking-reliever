using System.Collections.Generic;

namespace Reliever.BeneficiaryDashboard.Bff.Domain;

/// <summary>
/// FIFO bounded set with age expiry.
/// Used by AGG.CHN.001.DSH.BENEFICIARY_DASHBOARD.last_processed_event_ids
/// to back INV.DSH.002 (idempotency over the at-least-once bus).
///
/// Per process/CAP.CHN.001.DSH/aggregates.yaml, the field is bounded at
/// { count: 200, age: 30d } — the same defaults this set ships with.
/// Both bounds are applied write-side: on Add, expired entries are
/// pruned by insertion timestamp, then if size still exceeds <see cref="_maxCount"/>
/// the oldest entries are evicted.
///
/// Thread-safety: the caller (BeneficiaryDashboard.ApplyXxx) holds the
/// per-aggregate write lock — no internal locking here.
/// </summary>
public sealed class BoundedSet<T>
    where T : notnull
{
    private readonly int _maxCount;
    private readonly TimeSpan _maxAge;
    private readonly LinkedList<(T Value, DateTime InsertedAt)> _order = new();
    private readonly Dictionary<T, LinkedListNode<(T Value, DateTime InsertedAt)>> _index = new();

    public BoundedSet(int maxCount, TimeSpan maxAge)
    {
        _maxCount = maxCount;
        _maxAge = maxAge;
    }

    public int Count => _index.Count;

    public bool Contains(T value, DateTime now)
    {
        EvictExpired(now);
        return _index.ContainsKey(value);
    }

    /// <summary>
    /// Inserts <paramref name="value"/> if not already present.
    /// Returns true when the value was newly inserted, false if it was
    /// already a member of the set (idempotency hit — INV.DSH.002).
    /// </summary>
    public bool TryAdd(T value, DateTime now)
    {
        EvictExpired(now);
        if (_index.ContainsKey(value))
        {
            return false;
        }

        var node = _order.AddLast((value, now));
        _index[value] = node;

        while (_order.Count > _maxCount)
        {
            var first = _order.First!;
            _order.RemoveFirst();
            _index.Remove(first.Value.Value);
        }

        return true;
    }

    private void EvictExpired(DateTime now)
    {
        while (_order.First is { } first && (now - first.Value.InsertedAt) > _maxAge)
        {
            _order.RemoveFirst();
            _index.Remove(first.Value.Value);
        }
    }
}
