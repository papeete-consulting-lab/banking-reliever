using System.Globalization;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

namespace Reliever.BeneficiaryDashboard.Bff.Domain;

/// <summary>
/// AGG.CHN.001.DSH.BENEFICIARY_DASHBOARD — the consistency boundary of
/// CAP.CHN.001.DSH. One instance per <c>case_id</c>. Lazily materialised on
/// the first accepted command (INV.DSH.006). Updated by the three policy
/// commands (SYNCHRONIZE_SCORE / SYNCHRONIZE_TIER / RECORD_ENVELOPE_CONSUMPTION).
///
/// Invariants enforced here (process/CAP.CHN.001.DSH/aggregates.yaml):
///   INV.DSH.001 — PII exclusion (state contains only opaque ids, semantic
///                  labels, numeric amounts and ISO timestamps; PII filtering
///                  on inbound payloads happens upstream in
///                  Domain/Validators/PiiClassificationScanner before any
///                  Apply* call is made).
///   INV.DSH.002 — Idempotency on upstream event_id (bounded set).
///   INV.DSH.003 — Monotonic timestamps on score / tier.
///   INV.DSH.005 — recent_transactions bounded at 50 / 30d, FIFO.
///   INV.DSH.006 — lazy materialisation (the store calls the constructor on
///                  the first ApplyXxx for a case_id).
///
/// Snapshotting: every <see cref="_options.SnapshotEveryNEvents"/> applied
/// commands the aggregate increments a monotonic counter; the actual
/// persistence is out of scope for TASK-002 (no Mongo / no disk — in-memory
/// only). The hook is wired so TASK-006 can attach a persistent outbox.
///
/// Thread-safety: the aggregate keeps a per-instance write lock; readers
/// observe a consistent snapshot via <see cref="GetView"/> (which acquires
/// the same lock).
/// </summary>
public sealed class BeneficiaryDashboard
{
    private readonly object _lock = new();
    private readonly AggregateOptions _options;
    private readonly BoundedSet<string> _processedEventIds;
    private readonly BoundedFifoList<TransactionEntry> _recentTransactions;
    private readonly Dictionary<string, EnvelopeSnapshot> _openEnvelopes = new();

    private string? _currentTierCode;
    private DateTime? _tierUpgradedAt;
    private decimal? _currentScore;
    private DateTime? _scoreRecomputedAt;
    private DateTime? _lastViewedAt;
    private long _appliedEventCount;
    private string _etag = string.Empty;

    public BeneficiaryDashboard(string caseId, AggregateOptions options)
    {
        CaseId = caseId;
        _options = options;
        _processedEventIds = new BoundedSet<string>(
            options.ProcessedEventIdsBound,
            TimeSpan.FromDays(options.ProcessedEventIdsAgeDays));
        _recentTransactions = new BoundedFifoList<TransactionEntry>(
            options.RecentTransactionsBound,
            TimeSpan.FromDays(options.RecentTransactionsAgeDays),
            t => t.RecordedAt);
        _etag = ComputeEtag();
    }

    public string CaseId { get; }

    /// <summary>Current ETag of the GET /dashboard projection (hex sha-256 prefix).</summary>
    public string ETag
    {
        get { lock (_lock) { return _etag; } }
    }

    /// <summary>
    /// Snapshot view served by the GET /dashboard endpoint. Returns
    /// nullable fields untouched until populated by the first matching event.
    /// </summary>
    public DashboardSnapshot GetView()
    {
        lock (_lock)
        {
            DateTime? lastSyncedAt = new[]
            {
                _scoreRecomputedAt,
                _tierUpgradedAt,
                _openEnvelopes.Count == 0
                    ? (DateTime?)null
                    : _openEnvelopes.Values.Max(e => e.LastUpdatedAt),
            }.Where(d => d.HasValue).Max();

            return new DashboardSnapshot(
                CaseId: CaseId,
                CurrentTierCode: _currentTierCode,
                TierUpgradedAt: _tierUpgradedAt,
                CurrentScore: _currentScore,
                ScoreRecomputedAt: _scoreRecomputedAt,
                OpenEnvelopes: _openEnvelopes.Values
                    .OrderBy(e => e.EnvelopeId, StringComparer.Ordinal)
                    .ToList(),
                LastSyncedAt: lastSyncedAt,
                ETag: _etag);
        }
    }

    /// <summary>
    /// Snapshot of the recent_transactions feed (TASK-004 surfaces this via a query).
    /// </summary>
    public IReadOnlyList<TransactionEntry> GetRecentTransactions()
    {
        lock (_lock) { return _recentTransactions.Snapshot(); }
    }

    public CommandOutcome ApplySynchronizeScore(
        string eventId,
        decimal scoreValue,
        DateTime recomputedAt,
        DateTime now)
    {
        lock (_lock)
        {
            if (!_processedEventIds.TryAdd(eventId, now))
            {
                return CommandOutcome.EventAlreadyProcessed;
            }

            if (_scoreRecomputedAt is { } existing && recomputedAt < existing)
            {
                // INV.DSH.003 — out-of-order ack-and-drop.
                return CommandOutcome.StaleEvent;
            }

            _currentScore = scoreValue;
            _scoreRecomputedAt = recomputedAt;
            OnApplied();
            return CommandOutcome.Applied;
        }
    }

    public CommandOutcome ApplySynchronizeTier(
        string eventId,
        string currentTierCode,
        DateTime upgradedAt,
        DateTime now)
    {
        lock (_lock)
        {
            if (!_processedEventIds.TryAdd(eventId, now))
            {
                return CommandOutcome.EventAlreadyProcessed;
            }

            if (_tierUpgradedAt is { } existing && upgradedAt < existing)
            {
                return CommandOutcome.StaleEvent;
            }

            _currentTierCode = currentTierCode;
            _tierUpgradedAt = upgradedAt;
            OnApplied();
            return CommandOutcome.Applied;
        }
    }

    public CommandOutcome ApplyRecordEnvelopeConsumption(
        string eventId,
        string envelopeId,
        string transactionId,
        string category,
        decimal amount,
        decimal allocatedAmount,
        decimal consumedAmount,
        decimal availableAmount,
        string currency,
        string? merchantLabel,
        DateTime recordedAt,
        DateTime now)
    {
        lock (_lock)
        {
            if (!_processedEventIds.TryAdd(eventId, now))
            {
                return CommandOutcome.EventAlreadyProcessed;
            }

            // Refresh / insert the envelope snapshot.
            _openEnvelopes[envelopeId] = new EnvelopeSnapshot(
                EnvelopeId: envelopeId,
                Category: category,
                AllocatedAmount: allocatedAmount,
                ConsumedAmount: consumedAmount,
                AvailableAmount: availableAmount,
                Currency: currency,
                LastUpdatedAt: recordedAt);

            // Append to the recent_transactions feed (INV.DSH.005).
            _recentTransactions.Add(
                new TransactionEntry(
                    TransactionId: transactionId,
                    EnvelopeId: envelopeId,
                    Category: category,
                    Amount: amount,
                    Currency: currency,
                    MerchantLabel: merchantLabel,
                    RecordedAt: recordedAt),
                now);

            OnApplied();
            return CommandOutcome.Applied;
        }
    }

    public CommandOutcome ApplyRecordDashboardView(DateTime now)
    {
        // TASK-005 — Epic 4 surfaces this. Kept here so the aggregate is
        // ready to absorb the command and INV.DSH.004 (30s debounce) can
        // be implemented without re-wiring.
        lock (_lock)
        {
            _lastViewedAt = now;
            OnApplied();
            return CommandOutcome.Applied;
        }
    }

    private void OnApplied()
    {
        _appliedEventCount++;
        _etag = ComputeEtag();

        if (_appliedEventCount % _options.SnapshotEveryNEvents == 0)
        {
            // Hook for TASK-006 — persistent snapshot to outbox. In TASK-002
            // we only count, leaving the in-memory state authoritative.
        }
    }

    private string ComputeEtag()
    {
        // Deterministic ETag — same logical state yields the same etag.
        // We hash a canonical stringification of the snapshot fields. Used
        // by GET /dashboard to drive 304-on-If-None-Match (ADR-TECH-TACT-001
        // 5s polling — most responses are 304).
        var sb = new StringBuilder();
        sb.Append(CaseId).Append('|');
        sb.Append(_currentTierCode ?? "_").Append('|');
        sb.Append(_tierUpgradedAt?.ToString("o", CultureInfo.InvariantCulture) ?? "_").Append('|');
        sb.Append(_currentScore?.ToString(CultureInfo.InvariantCulture) ?? "_").Append('|');
        sb.Append(_scoreRecomputedAt?.ToString("o", CultureInfo.InvariantCulture) ?? "_").Append('|');
        foreach (var env in _openEnvelopes.Values.OrderBy(e => e.EnvelopeId, StringComparer.Ordinal))
        {
            sb.Append(env.EnvelopeId).Append(':')
              .Append(env.ConsumedAmount.ToString(CultureInfo.InvariantCulture)).Append(':')
              .Append(env.AvailableAmount.ToString(CultureInfo.InvariantCulture)).Append(':')
              .Append(env.LastUpdatedAt.ToString("o", CultureInfo.InvariantCulture)).Append(';');
        }

        Span<byte> hash = stackalloc byte[32];
        SHA256.HashData(Encoding.UTF8.GetBytes(sb.ToString()), hash);
        return Convert.ToHexString(hash[..8]).ToLowerInvariant();
    }
}

/// <summary>
/// Materialised dashboard projection — what GET /dashboard returns.
/// Mirrors PRJ.CHN.001.DSH.DASHBOARD_VIEW from read-models.yaml.
/// </summary>
public sealed record DashboardSnapshot(
    string CaseId,
    string? CurrentTierCode,
    DateTime? TierUpgradedAt,
    decimal? CurrentScore,
    DateTime? ScoreRecomputedAt,
    IReadOnlyList<EnvelopeSnapshot> OpenEnvelopes,
    DateTime? LastSyncedAt,
    string ETag);
