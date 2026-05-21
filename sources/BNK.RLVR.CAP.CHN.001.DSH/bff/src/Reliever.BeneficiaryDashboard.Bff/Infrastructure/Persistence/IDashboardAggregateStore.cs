using Reliever.BeneficiaryDashboard.Bff.Domain;

namespace Reliever.BeneficiaryDashboard.Bff.Infrastructure.Persistence;

/// <summary>
/// Lookup contract for the singleton in-memory store of
/// AGG.CHN.001.DSH.BENEFICIARY_DASHBOARD instances.
///
/// INV.DSH.006 — lazy materialisation: <see cref="GetOrCreate"/> creates
/// the aggregate on first call for a given <c>case_id</c>; <see cref="TryGet"/>
/// never materialises.
///
/// Persistence is out of scope for TASK-002 (see README — A1). TASK-006
/// will swap this implementation for one backed by an outbox-friendly store.
/// </summary>
public interface IDashboardAggregateStore
{
    Domain.BeneficiaryDashboard GetOrCreate(string caseId);
    bool TryGet(string caseId, out Domain.BeneficiaryDashboard? aggregate);
    int Count { get; }
}
