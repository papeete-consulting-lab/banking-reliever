using System.Text;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using RabbitMQ.Client;

namespace Reliever.TierManagement.Stub;

/// <summary>
/// Background worker that publishes simulated BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED
/// messages on the RabbitMQ topic exchange owned by BNK.RLVR.CAP.BSP.001.TIE.
///
/// Inactive by default (StubOptions.Active=false). Activate via env var STUB_ACTIVE=true
/// or by setting Stub:Active=true in configuration. Inactive in production.
/// </summary>
public sealed class Worker : BackgroundService
{
    private readonly StubOptions _options;
    private readonly PayloadFactory _payloadFactory;
    private readonly SchemaValidator _validator;
    private readonly ILogger<Worker> _logger;

    public Worker(
        IOptions<StubOptions> options,
        PayloadFactory payloadFactory,
        SchemaValidator validator,
        ILogger<Worker> logger)
    {
        _options = options.Value;
        _payloadFactory = payloadFactory;
        _validator = validator;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        if (!_options.Active)
        {
            _logger.LogWarning(
                "Stub started in INACTIVE mode (Stub:Active=false). " +
                "No messages will be published. Set STUB_ACTIVE=true to enable. " +
                "Reminder: this stub MUST remain inactive in production.");
            // Stay alive so the host keeps running (useful for ops introspection),
            // but emit nothing.
            await Task.Delay(Timeout.Infinite, stoppingToken).ConfigureAwait(false);
            return;
        }

        // Validate cadence per DoD: 1..10/min default; outside requires explicit override.
        ValidateCadence();

        var periodMs = (int)Math.Round(60_000.0 / _options.EventsPerMinute);
        _logger.LogInformation(
            "Stub ACTIVE — exchange='{Exchange}' routingKey='{RoutingKey}' cadence={Cadence}/min (period={Period}ms)",
            _options.Bus.ExchangeName, _options.Bus.RoutingKey, _options.EventsPerMinute, periodMs);

        var factory = new ConnectionFactory
        {
            HostName = _options.RabbitMq.HostName,
            Port = _options.RabbitMq.Port,
            UserName = _options.RabbitMq.UserName,
            Password = _options.RabbitMq.Password,
            VirtualHost = _options.RabbitMq.VirtualHost
        };

        await using var connection = await factory.CreateConnectionAsync(stoppingToken).ConfigureAwait(false);
        await using var channel = await connection.CreateChannelAsync(cancellationToken: stoppingToken).ConfigureAwait(false);

        // ADR-TECH-STRAT-001 Rule 1, 5 — declare the topic exchange owned by BNK.RLVR.CAP.BSP.001.TIE.
        await channel.ExchangeDeclareAsync(
            exchange: _options.Bus.ExchangeName,
            type: ExchangeType.Topic,
            durable: true,
            autoDelete: false,
            arguments: null,
            cancellationToken: stoppingToken).ConfigureAwait(false);

        _logger.LogInformation(
            "Topic exchange '{Exchange}' declared. Beginning publication loop.",
            _options.Bus.ExchangeName);

        var rotation = 0;
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                var (payloadJson, caseId) = _payloadFactory.BuildNext(rotation++);

                // Fail-fast validation against the runtime schema (DoD: every payload validated).
                _validator.Validate(payloadJson);

                var props = new BasicProperties
                {
                    ContentType = "application/json",
                    DeliveryMode = DeliveryModes.Persistent,
                    MessageId = Guid.NewGuid().ToString("N"),
                    Timestamp = new AmqpTimestamp(DateTimeOffset.UtcNow.ToUnixTimeSeconds()),
                    Type = "BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED",
                    Headers = new Dictionary<string, object?>
                    {
                        ["x-bcm-business-event"] = "BNK.RLVR.EVT.BSP.001.TIER_UPGRADED",
                        ["x-bcm-resource-event"] = "BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED",
                        ["x-bcm-emitting-capability"] = "BNK.RLVR.CAP.BSP.001.TIE",
                        ["x-bcm-version"] = "1.0.0"
                    }
                };

                var body = Encoding.UTF8.GetBytes(payloadJson);

                await channel.BasicPublishAsync(
                    exchange: _options.Bus.ExchangeName,
                    routingKey: _options.Bus.RoutingKey,
                    mandatory: false,
                    basicProperties: props,
                    body: body,
                    cancellationToken: stoppingToken).ConfigureAwait(false);

                _logger.LogInformation(
                    "Published BNK.RLVR.RVT.BSP.001.TIER_UPGRADE_RECORDED for case={CaseId}",
                    caseId);
            }
            catch (SchemaValidationException ex)
            {
                _logger.LogError(ex,
                    "Schema validation failed — payload NOT published. This is a stub bug; halting publication loop to surface the defect.");
                throw;
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Unexpected error during publication; will retry after the cadence period.");
            }

            try
            {
                await Task.Delay(periodMs, stoppingToken).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                break;
            }
        }

        _logger.LogInformation("Stub publication loop stopped.");
    }

    private void ValidateCadence()
    {
        const double Min = 1.0;
        const double Max = 10.0;
        if (_options.EventsPerMinute < Min || _options.EventsPerMinute > Max)
        {
            if (!_options.AllowOutOfRangeCadence)
            {
                throw new InvalidOperationException(
                    $"EventsPerMinute={_options.EventsPerMinute} is outside the default range [1, 10]. " +
                    "Set Stub:AllowOutOfRangeCadence=true (or STUB_AllowOutOfRangeCadence=true) " +
                    "to explicitly override per Definition of Done.");
            }
            _logger.LogWarning(
                "Cadence override active: {Cadence}/min is outside the default [1, 10] range. AllowOutOfRangeCadence=true.",
                _options.EventsPerMinute);
        }

        if (_options.EventsPerMinute <= 0)
        {
            throw new InvalidOperationException("EventsPerMinute must be strictly positive.");
        }
    }
}
