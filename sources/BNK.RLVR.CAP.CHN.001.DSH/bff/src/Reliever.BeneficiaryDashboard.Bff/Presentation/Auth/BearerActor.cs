using System.IdentityModel.Tokens.Jwt;

namespace Reliever.BeneficiaryDashboard.Bff.Presentation.Auth;

/// <summary>
/// Channel-side actor extraction from the Authorization bearer token.
///
/// Per ADR-TECH-STRAT-003 bi-layer security: the upstream gateway
/// validates the JWT signature; the BFF re-extracts the actor (sub
/// claim) and enforces sub == case_id-owner. For TASK-002 / dev mode
/// the BFF accepts any well-formed JWT and records the sub claim as
/// the actor. Production deployment wires
/// AddAuthentication().AddJwtBearer(...) per the L2 tactical ADR.
///
/// Negative behaviour (TASK-002 — *dev permissive*):
///   - missing Authorization header     → Actor = null (treated as anonymous dev request)
///   - malformed JWT (not three dot-segments / not base64) → Actor = null
///   - sub claim missing                → Actor = null
/// Production behaviour (TODO):
///   - missing / invalid bearer → 401
///   - sub claim missing        → 401
///   - sub != case_id-owner     → 403
/// </summary>
public sealed record BearerActor(string? Sub);

public static class BearerActorExtractor
{
    public static BearerActor From(HttpContext context)
    {
        var authz = context.Request.Headers.Authorization.ToString();
        if (string.IsNullOrWhiteSpace(authz)
            || !authz.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
        {
            return new BearerActor(null);
        }

        var token = authz["Bearer ".Length..].Trim();
        try
        {
            var jwt = new JwtSecurityToken(token);
            var sub = jwt.Subject ?? jwt.Claims.FirstOrDefault(c => c.Type == "sub")?.Value;
            return new BearerActor(sub);
        }
        catch
        {
            return new BearerActor(null);
        }
    }
}
