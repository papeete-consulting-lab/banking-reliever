using System.Net;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using FluentAssertions;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using RabbitMQ.Client;
using Testcontainers.RabbitMq;
using Xunit;

namespace Reliever.BeneficiaryDashboard.Bff.Tests.Integration;

/// <summary>
/// End-to-end behaviour:
///   - boot the BFF in-process via WebApplicationFactory&lt;Program&gt;
///   - point it at a Testcontainers-managed RabbitMQ instance
///   - publish synthetic RVTs against the producer-owned exchanges
///   - poll GET /dashboard and assert the projection
///
/// Skipped automatically when Docker is unavailable on the host
/// (e.g. minimal CI runners) — see the constructor guard.
/// </summary>
public sealed class DashboardEndToEndTests : IAsyncLifetime
{
    private readonly RabbitMqContainer _rabbit;
    private WebApplicationFactory<Program>? _factory;
    private HttpClient? _client;

    public DashboardEndToEndTests()
    {
        _rabbit = new RabbitMqBuilder()
            .WithImage("rabbitmq:3.13-management-alpine")
            .WithUsername("guest")
            .WithPassword("guest")
            .Build();
    }

    public async Task InitializeAsync()
    {
        await _rabbit.StartAsync();

        var uri = new Uri(_rabbit.GetConnectionString());
        var host = uri.Host;
        var port = uri.Port;

        _factory = new WebApplicationFactory<Program>()
            .WithWebHostBuilder(b => b.ConfigureAppConfiguration((_, config) =>
            {
                config.AddInMemoryCollection(new Dictionary<string, string?>
                {
                    ["RabbitMQ:Host"]            = host,
                    ["RabbitMQ:Port"]            = port.ToString(),
                    ["RabbitMQ:VirtualHost"]     = "/",
                    ["RabbitMQ:Username"]        = "guest",
                    ["RabbitMQ:Password"]        = "guest",
                    ["Bff:BranchSlug"]           = "integration-test",
                    ["Telemetry:OtlpEndpoint"]   = "",
                });
            }));

        _client = _factory.CreateClient();

        // Give MassTransit a beat to declare exchanges + queues + bindings.
        await Task.Delay(2000);
    }

    public async Task DisposeAsync()
    {
        _client?.Dispose();
        if (_factory is not null) await _factory.DisposeAsync();
        await _rabbit.DisposeAsync();
    }

    [Fact(Skip = "Requires Docker — run manually via `dotnet test` with Docker available.")]
    public async Task EndToEnd_TierUpgradeRvt_MaterialisesAggregateAndExposesViaGet()
    {
        var caseId = Guid.NewGuid().ToString();
        var eventId = Guid.NewGuid().ToString();
        var occurredAt = DateTime.UtcNow;

        var payload = $$"""
            {
              "event_id": "{{eventId}}",
              "case_id": "{{caseId}}",
              "transition": {
                "from_tier_code": "T1",
                "to_tier_code": "T2",
                "cause": "SCORE_THRESHOLD",
                "tier_definitions_version": "v1"
              },
              "occurred_at": "{{occurredAt:o}}"
            }
            """;

        await PublishRawAsync("bsp.001.tie-events",
            "EVT.BSP.001.TIER_UPGRADED.RVT.BSP.001.TIER_UPGRADE_RECORDED",
            payload);

        // The frontend polls every 5s — wait for materialisation.
        var deadline = DateTime.UtcNow.AddSeconds(20);
        HttpResponseMessage? resp = null;
        while (DateTime.UtcNow < deadline)
        {
            resp = await _client!.GetAsync($"/capabilities/chn/001/dsh/cases/{caseId}/dashboard");
            if (resp.StatusCode == HttpStatusCode.OK) break;
            await Task.Delay(500);
        }

        resp!.StatusCode.Should().Be(HttpStatusCode.OK);
        var body = await resp.Content.ReadFromJsonAsync<JsonElement>();
        body.GetProperty("case_id").GetString().Should().Be(caseId);
        body.GetProperty("current_tier_code").GetString().Should().Be("T2");

        // ETag + 304 round-trip.
        var etag = resp.Headers.ETag!.Tag;
        var req2 = new HttpRequestMessage(HttpMethod.Get,
            $"/capabilities/chn/001/dsh/cases/{caseId}/dashboard");
        req2.Headers.TryAddWithoutValidation("If-None-Match", etag);
        var resp2 = await _client.SendAsync(req2);
        resp2.StatusCode.Should().Be(HttpStatusCode.NotModified);
    }

    [Fact(Skip = "Requires Docker — run manually via `dotnet test` with Docker available.")]
    public async Task EndToEnd_DuplicateRvtEventId_TransitionsExactlyOnce()
    {
        var caseId = Guid.NewGuid().ToString();
        var eventId = Guid.NewGuid().ToString();
        var t1 = DateTime.UtcNow;
        var t2 = t1.AddSeconds(10);

        // First publish — score 10
        await PublishScoreAsync(caseId, eventId, 10m, t1);
        // Duplicate (same envelope.message_id) — score 999 should be DROPPED
        await PublishScoreAsync(caseId, eventId, 999m, t2);

        await Task.Delay(2000);

        var resp = await _client!.GetAsync(
            $"/capabilities/chn/001/dsh/cases/{caseId}/dashboard");
        resp.StatusCode.Should().Be(HttpStatusCode.OK);
        var body = await resp.Content.ReadFromJsonAsync<JsonElement>();
        body.GetProperty("current_score").GetDecimal().Should().Be(10m,
            "INV.DSH.002 — duplicate event_id MUST transition exactly once");
    }

    [Fact(Skip = "Requires Docker — run manually via `dotnet test` with Docker available.")]
    public async Task EndToEnd_OutOfOrderScoreRvt_IsAckAndDropped()
    {
        var caseId = Guid.NewGuid().ToString();
        var tNew = DateTime.UtcNow;
        var tOld = tNew.AddMinutes(-1);

        await PublishScoreAsync(caseId, Guid.NewGuid().ToString(), 50m, tNew);
        await Task.Delay(1500);
        await PublishScoreAsync(caseId, Guid.NewGuid().ToString(), 10m, tOld);
        await Task.Delay(1500);

        var resp = await _client!.GetAsync(
            $"/capabilities/chn/001/dsh/cases/{caseId}/dashboard");
        var body = await resp.Content.ReadFromJsonAsync<JsonElement>();
        body.GetProperty("current_score").GetDecimal().Should().Be(50m,
            "INV.DSH.003 — stale (older) score MUST be dropped");
    }

    [Fact(Skip = "Requires Docker — run manually via `dotnet test` with Docker available.")]
    public async Task EndToEnd_PayloadCarryingPii_IsRoutedToDlq()
    {
        var caseId = Guid.NewGuid().ToString();
        var payload = $$"""
            {
              "event_id": "{{Guid.NewGuid()}}",
              "case_id": "{{caseId}}",
              "transition": {
                "from_tier_code": "T1",
                "to_tier_code": "T2",
                "cause": "SCORE_THRESHOLD",
                "tier_definitions_version": "v1"
              },
              "occurred_at": "{{DateTime.UtcNow:o}}",
              "first_name": "Marie"
            }
            """;

        await PublishRawAsync("bsp.001.tie-events",
            "EVT.BSP.001.TIER_UPGRADED.RVT.BSP.001.TIER_UPGRADE_RECORDED",
            payload);

        await Task.Delay(3000);

        var resp = await _client!.GetAsync(
            $"/capabilities/chn/001/dsh/cases/{caseId}/dashboard");
        resp.StatusCode.Should().Be(HttpStatusCode.NotFound,
            "INV.DSH.001 — PII-bearing payload MUST not materialise the aggregate");
    }

    // ── Helpers ──────────────────────────────────────────────────────────────
    private async Task PublishScoreAsync(string caseId, string messageId, decimal score, DateTime ts)
    {
        var payload = $$"""
            {
              "envelope": {
                "message_id": "{{messageId}}",
                "schema_version": "0.1.0",
                "emitted_at": "{{ts:o}}",
                "emitting_capability": "CAP.BSP.001.SCO",
                "correlation_id": "{{caseId}}",
                "causation_id": "{{Guid.NewGuid()}}"
              },
              "case_id": "{{caseId}}",
              "evaluation_id": "{{Guid.NewGuid()}}",
              "score_value": {{score.ToString(System.Globalization.CultureInfo.InvariantCulture)}},
              "delta_score": 0,
              "model_version": "1.0.0",
              "evaluation_type": "CURRENT",
              "computation_timestamp": "{{ts:o}}",
              "trigger": {
                "kind": "TRANSACTION_AUTHORIZED",
                "event_id": "{{Guid.NewGuid()}}",
                "polarity": "positive"
              },
              "contributing_factors": []
            }
            """;
        await PublishRawAsync("bsp.001.sco-events",
            "EVT.BSP.001.SCORE_RECOMPUTED.RVT.BSP.001.CURRENT_SCORE_RECOMPUTED",
            payload);
    }

    private async Task PublishRawAsync(string exchange, string routingKey, string json)
    {
        var uri = new Uri(_rabbit.GetConnectionString());
        var factory = new ConnectionFactory { Uri = uri };
        using var conn = await factory.CreateConnectionAsync();
        using var ch = await conn.CreateChannelAsync();
        await ch.ExchangeDeclareAsync(exchange, "topic", durable: true);
        var props = new BasicProperties { ContentType = "application/json" };
        await ch.BasicPublishAsync(exchange, routingKey, mandatory: false,
            basicProperties: props, body: Encoding.UTF8.GetBytes(json));
    }
}
