namespace Reliever.BeneficiaryDashboard.Bff.Domain;

/// <summary>
/// Outcome of a command applied to AGG.BENEFICIARY_DASHBOARD.
/// Matches the error codes declared in
/// process/CAP.CHN.001.DSH/commands.yaml — only the ones reachable in
/// TASK-002 scope (the three SYNCHRONIZE_* / RECORD_ENVELOPE_CONSUMPTION
/// commands). Each maps deterministically to a policy action:
/// </summary>
public enum CommandOutcome
{
    /// <summary>State mutated; ETag advanced.</summary>
    Applied,

    /// <summary>
    /// INV.DSH.002 — event_id already in last_processed_event_ids.
    /// Policy ack-and-drops (silent absorb of at-least-once replay).
    /// </summary>
    EventAlreadyProcessed,

    /// <summary>
    /// INV.DSH.003 — trigger.*_at older than locally observed *_at.
    /// Policy ack-and-drops (out-of-order delivery is expected, not pathological).
    /// </summary>
    StaleEvent,
}
