using Reliever.BeneficiaryDashboard.Bff.Contracts.ApiModels;
using Reliever.BeneficiaryDashboard.Bff.Infrastructure.Persistence;
using Reliever.BeneficiaryDashboard.Bff.Presentation.Auth;

namespace Reliever.BeneficiaryDashboard.Bff.Presentation.Routers;

/// <summary>
/// HTTP surface declared by process/CAP.CHN.001.DSH/api.yaml:
///   GET  /capabilities/chn/001/dsh/cases/{case_id}/dashboard         — TASK-002 (this task)
///   GET  /capabilities/chn/001/dsh/cases/{case_id}/transactions      — TASK-004 (501 stub here)
///   POST /capabilities/chn/001/dsh/cases/{case_id}/dashboard-views   — TASK-005 (501 stub here)
///   GET  /health                                                     — readiness probe
/// </summary>
public static class DashboardRouter
{
    public const string BasePath = "/capabilities/chn/001/dsh";

    public static IEndpointRouteBuilder MapDashboardRoutes(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup(BasePath);

        group.MapGet("/cases/{caseId}/dashboard", GetDashboard)
            .WithName("getDashboard")
            .WithDescription("Returns the synthesised PII-free dashboard projection. ETag/304 + 5s max-age.");

        group.MapGet("/cases/{caseId}/transactions", GetTransactions)
            .WithName("listRecentTransactions")
            .WithDescription("Recent transactions feed (TASK-004 — stub returns 501 NOT IMPLEMENTED).");

        group.MapPost("/cases/{caseId}/dashboard-views", PostDashboardView)
            .WithName("recordDashboardView")
            .WithDescription("Records a dashboard consultation (TASK-005 / Epic 4 — stub returns 501 NOT IMPLEMENTED).");

        return app;
    }

    // ── GET /dashboard ─────────────────────────────────────────────────────
    private static IResult GetDashboard(
        string caseId,
        HttpContext context,
        IDashboardAggregateStore store)
    {
        if (string.IsNullOrWhiteSpace(caseId))
        {
            return Results.BadRequest(new { error = "case_id is required" });
        }

        // Channel-side actor extraction (dev-permissive — see BearerActor).
        var actor = BearerActorExtractor.From(context);
        // TODO (prod): if (actor.Sub is null || !ResolveOwner(caseId).Equals(actor.Sub)) return Results.Forbid();

        if (!store.TryGet(caseId, out var aggregate) || aggregate is null)
        {
            return Results.NotFound(new
            {
                error = "DASHBOARD_NOT_MATERIALIZED",
                case_id = caseId,
                hint = "No upstream RVT has been received for this case_id yet.",
            });
        }

        var snapshot = aggregate.GetView();

        // ETag / If-None-Match handling (TECH-STRAT-003 + ADR-TECH-TACT-001).
        var quoted = $"\"{snapshot.ETag}\"";
        var ifNoneMatch = context.Request.Headers.IfNoneMatch.ToString().Trim();
        if (!string.IsNullOrEmpty(ifNoneMatch) &&
            (ifNoneMatch == quoted || ifNoneMatch == snapshot.ETag))
        {
            context.Response.Headers.ETag = quoted;
            context.Response.Headers.CacheControl = "private, max-age=5";
            return Results.StatusCode(StatusCodes.Status304NotModified);
        }

        var view = new DashboardView(
            CaseId: snapshot.CaseId,
            CurrentTierCode: snapshot.CurrentTierCode,
            TierUpgradedAt: snapshot.TierUpgradedAt,
            CurrentScore: snapshot.CurrentScore,
            ScoreRecomputedAt: snapshot.ScoreRecomputedAt,
            OpenEnvelopes: snapshot.OpenEnvelopes
                .Select(e => new DashboardEnvelopeView(
                    EnvelopeId: e.EnvelopeId,
                    Category: e.Category,
                    AllocatedAmount: e.AllocatedAmount,
                    ConsumedAmount: e.ConsumedAmount,
                    AvailableAmount: e.AvailableAmount,
                    Currency: e.Currency,
                    LastUpdatedAt: e.LastUpdatedAt))
                .ToList(),
            LastSyncedAt: snapshot.LastSyncedAt);

        context.Response.Headers.ETag = quoted;
        context.Response.Headers.CacheControl = "private, max-age=5";
        return Results.Ok(view);
    }

    // ── GET /transactions — TASK-004 stub ─────────────────────────────────
    private static IResult GetTransactions(string caseId, HttpContext context)
    {
        context.Response.Headers.CacheControl = "no-store";
        return Results.StatusCode(StatusCodes.Status501NotImplemented);
    }

    // ── POST /dashboard-views — TASK-005 stub ─────────────────────────────
    private static IResult PostDashboardView(string caseId, HttpContext context)
    {
        context.Response.Headers.CacheControl = "no-store";
        return Results.StatusCode(StatusCodes.Status501NotImplemented);
    }
}
