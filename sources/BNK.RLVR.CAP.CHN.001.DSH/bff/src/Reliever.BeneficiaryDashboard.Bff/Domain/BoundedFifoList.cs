using System.Collections.Generic;
using System.Linq;

namespace Reliever.BeneficiaryDashboard.Bff.Domain;

/// <summary>
/// Most-recent-first bounded list with age expiry.
/// Backs AGG.CHN.001.DSH.BENEFICIARY_DASHBOARD.recent_transactions per
/// INV.DSH.005: max 50 entries, max age 30d, FIFO eviction on
/// <c>recorded_at</c>.
///
/// The list is kept sorted most-recent-first by <c>recorded_at</c>.
/// Entries older than <see cref="_maxAge"/> are evicted relative to
/// <c>now</c> at every Add call (not relative to the head). If size
/// still exceeds <see cref="_maxCount"/> after age eviction, the
/// oldest entries are dropped to fit.
///
/// Thread-safety: caller-held lock (per-aggregate write lock).
/// </summary>
public sealed class BoundedFifoList<T>
    where T : class
{
    private readonly int _maxCount;
    private readonly TimeSpan _maxAge;
    private readonly Func<T, DateTime> _recordedAt;
    private readonly List<T> _items = new();

    public BoundedFifoList(int maxCount, TimeSpan maxAge, Func<T, DateTime> recordedAtSelector)
    {
        _maxCount = maxCount;
        _maxAge = maxAge;
        _recordedAt = recordedAtSelector;
    }

    public int Count => _items.Count;

    public IReadOnlyList<T> Snapshot() => _items.ToList();

    /// <summary>
    /// Inserts <paramref name="entry"/> at the position that keeps the
    /// list ordered most-recent-first. Applies age eviction first
    /// (relative to <paramref name="now"/>), then count eviction.
    /// </summary>
    public void Add(T entry, DateTime now)
    {
        // 1. Age eviction (INV.DSH.005 — strictly older than max age relative to now)
        _items.RemoveAll(e => (now - _recordedAt(e)) > _maxAge);

        // 2. Insert keeping the list sorted most-recent-first
        var entryTs = _recordedAt(entry);
        var insertIdx = _items.FindIndex(e => _recordedAt(e) <= entryTs);
        if (insertIdx < 0)
        {
            _items.Add(entry);
        }
        else
        {
            _items.Insert(insertIdx, entry);
        }

        // 3. Count eviction — drop oldest (tail) entries
        while (_items.Count > _maxCount)
        {
            _items.RemoveAt(_items.Count - 1);
        }
    }
}
