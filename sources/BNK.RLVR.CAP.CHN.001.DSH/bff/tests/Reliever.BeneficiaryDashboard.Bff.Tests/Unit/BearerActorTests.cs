using System.IdentityModel.Tokens.Jwt;
using FluentAssertions;
using Microsoft.AspNetCore.Http;
using Reliever.BeneficiaryDashboard.Bff.Presentation.Auth;
using Xunit;

namespace Reliever.BeneficiaryDashboard.Bff.Tests.Unit;

public class BearerActorTests
{
    [Fact]
    public void NoAuthorizationHeader_ReturnsNullSub()
    {
        var ctx = new DefaultHttpContext();
        var actor = BearerActorExtractor.From(ctx);
        actor.Sub.Should().BeNull();
    }

    [Fact]
    public void NonBearerScheme_ReturnsNullSub()
    {
        var ctx = new DefaultHttpContext();
        ctx.Request.Headers.Authorization = "Basic dXNlcjpwYXNz";
        var actor = BearerActorExtractor.From(ctx);
        actor.Sub.Should().BeNull();
    }

    [Fact]
    public void MalformedJwt_ReturnsNullSub()
    {
        var ctx = new DefaultHttpContext();
        ctx.Request.Headers.Authorization = "Bearer not.a.valid.jwt";
        var actor = BearerActorExtractor.From(ctx);
        actor.Sub.Should().BeNull();
    }

    [Fact]
    public void ValidJwtWithSub_ExtractsSub()
    {
        // Build an unsigned JWT with sub=beneficiary-42 (TASK-002 is dev-permissive
        // — production validates signature via JwtBearer middleware).
        var token = new JwtSecurityToken(
            issuer: "test",
            audience: "test",
            claims: new[] { new System.Security.Claims.Claim("sub", "beneficiary-42") });
        var raw = new JwtSecurityTokenHandler().WriteToken(token);

        var ctx = new DefaultHttpContext();
        ctx.Request.Headers.Authorization = $"Bearer {raw}";

        var actor = BearerActorExtractor.From(ctx);
        actor.Sub.Should().Be("beneficiary-42");
    }
}
