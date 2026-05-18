using System.Text.Json;
using MassTransit;
using Reliever.BeneficiaryDashboard.Bff.Application.Commands;
using Reliever.BeneficiaryDashboard.Bff.Consumers;
using Reliever.BeneficiaryDashboard.Bff.Domain;
using Reliever.BeneficiaryDashboard.Bff.Domain.Validators;
using Reliever.BeneficiaryDashboard.Bff.Infrastructure.Persistence;
using Reliever.BeneficiaryDashboard.Bff.Presentation.Routers;
using Reliever.BeneficiaryDashboard.Bff.Telemetry;

var builder = WebApplication.CreateBuilder(args);

// ── Configuration binding ────────────────────────────────────────────────────
builder.Services.Configure<AggregateOptions>(builder.Configuration.GetSection("Aggregate"));

// ── Telemetry (OTel) ──────────────────────────────────────────────────────────
builder.Services.AddDashboardTelemetry(builder.Configuration, builder.Environment);

// ── Time ──────────────────────────────────────────────────────────────────────
builder.Services.AddSingleton(TimeProvider.System);

// ── Aggregate store (singleton, in-memory) ────────────────────────────────────
builder.Services.AddSingleton<IDashboardAggregateStore, InMemoryDashboardAggregateStore>();
builder.Services.AddScoped<DashboardCommandHandlers>();

// ── Upstream schema validator (loaded once at startup, fail-fast) ─────────────
builder.Services.AddSingleton(_ => new UpstreamSchemaValidator(builder.Environment.ContentRootPath));

// ── Subscription bindings — produce branch-slug-suffixed queue names ─────────
var branchSlug = builder.Configuration["Bff:BranchSlug"]
                 ?? builder.Configuration["Telemetry:Environment"]
                 ?? "local";
var subs = builder.Configuration.GetSection("Subscriptions");
var queueScore     = $"chn.001.dsh.q.score-recomputed-{branchSlug}";
var queueTier      = $"chn.001.dsh.q.tier-upgraded-{branchSlug}";
var queueEnvelope  = $"chn.001.dsh.q.envelope-consumed-{branchSlug}";

// ── MassTransit / RabbitMQ ────────────────────────────────────────────────────
builder.Services.AddMassTransit(x =>
{
    x.AddConsumer<OnScoreRecomputedConsumer>();
    x.AddConsumer<OnTierUpgradeRecordedConsumer>();
    x.AddConsumer<OnEnvelopeConsumptionRecordedConsumer>();

    x.UsingRabbitMq((ctx, cfg) =>
    {
        var rabbit = builder.Configuration.GetSection("RabbitMQ");
        cfg.Host(
            rabbit["Host"] ?? "localhost",
            ushort.Parse(rabbit["Port"] ?? "5672"),
            rabbit["VirtualHost"] ?? "/",
            h =>
            {
                h.Username(rabbit["Username"] ?? "guest");
                h.Password(rabbit["Password"] ?? "guest");
            });

        // W3C traceparent propagation through RabbitMQ headers is enabled
        // by registering the "MassTransit" ActivitySource in TelemetrySetup
        // (MassTransit 8.x emits Activity spans natively; no extra configurator call needed).

        // ── SCO subscription ─────────────────────────────────────────────────
        cfg.ReceiveEndpoint(queueScore, e =>
        {
            // Upstream stub publishes raw JSON — bypass MassTransit envelope.
            e.ClearSerialization();
            e.UseRawJsonSerializer(RawSerializerOptions.AnyMessageType);

            e.Bind(subs["ScoreRecomputedExchange"]!, b =>
            {
                b.ExchangeType = "topic";
                b.RoutingKey   = subs["ScoreRecomputedBinding"]!;
                b.Durable      = true;
            });

            // Retry then DLQ — payload-shape errors land in {queue}_error.
            e.UseMessageRetry(r => r.Immediate(2));
            e.Consumer<OnScoreRecomputedConsumer>(ctx);
        });

        // ── TIE subscription ─────────────────────────────────────────────────
        cfg.ReceiveEndpoint(queueTier, e =>
        {
            e.ClearSerialization();
            e.UseRawJsonSerializer(RawSerializerOptions.AnyMessageType);

            e.Bind(subs["TierUpgradedExchange"]!, b =>
            {
                b.ExchangeType = "topic";
                b.RoutingKey   = subs["TierUpgradedBinding"]!;
                b.Durable      = true;
            });

            e.UseMessageRetry(r => r.Immediate(2));
            e.Consumer<OnTierUpgradeRecordedConsumer>(ctx);
        });

        // ── ENV subscription ─────────────────────────────────────────────────
        cfg.ReceiveEndpoint(queueEnvelope, e =>
        {
            e.ClearSerialization();
            e.UseRawJsonSerializer(RawSerializerOptions.AnyMessageType);

            e.Bind(subs["EnvelopeConsumedExchange"]!, b =>
            {
                b.ExchangeType = "topic";
                b.RoutingKey   = subs["EnvelopeConsumedBinding"]!;
                b.Durable      = true;
            });

            e.UseMessageRetry(r => r.Immediate(2));
            e.Consumer<OnEnvelopeConsumptionRecordedConsumer>(ctx);
        });
    });
});

// ── HTTP JSON options — camelCase off, snake_case via JsonPropertyName ────────
builder.Services.ConfigureHttpJsonOptions(o =>
{
    o.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower;
    o.SerializerOptions.DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.Never;
});

// ── CORS (vanilla-JS frontend served on a sibling dev port) ──────────────────
builder.Services.AddCors(options =>
    options.AddDefaultPolicy(policy =>
        policy.SetIsOriginAllowed(_ => true)
            .AllowAnyHeader()
            .AllowAnyMethod()
            .WithExposedHeaders("ETag")));

var app = builder.Build();

app.UseCors();

// ── TODO (production): wire AddAuthentication().AddJwtBearer(...) per
//      the L2 tactical ADR (ADR-TECH-TACT-001). Channel-side check enforces
//      sub == case_id-owner — see Presentation/Auth/BearerActor.cs.
// app.UseAuthentication();
// app.UseAuthorization();

app.MapDashboardRoutes();

app.MapGet("/health", () => Results.Ok(new
{
    status      = "ok",
    capability  = "CAP.CHN.001.DSH",
    branch_slug = branchSlug,
    queues      = new[] { queueScore, queueTier, queueEnvelope },
}));

app.Logger.LogInformation(
    "CAP.CHN.001.DSH BFF starting — branch_slug={Slug}, queues=[{Q1}, {Q2}, {Q3}]",
    branchSlug, queueScore, queueTier, queueEnvelope);

app.Run();

/// <summary>
/// Exposed so the integration test fixture can spin up the BFF in-process
/// via <c>WebApplicationFactory&lt;Program&gt;</c>.
/// </summary>
public partial class Program;
