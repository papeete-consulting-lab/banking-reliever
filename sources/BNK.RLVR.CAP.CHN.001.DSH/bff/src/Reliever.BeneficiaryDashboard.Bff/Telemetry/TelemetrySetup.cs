using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

namespace Reliever.BeneficiaryDashboard.Bff.Telemetry;

public static class TelemetrySetup
{
    public static IServiceCollection AddDashboardTelemetry(
        this IServiceCollection services,
        IConfiguration config,
        IHostEnvironment env)
    {
        var serviceName = config["Telemetry:ServiceName"] ?? "chn.001.dsh-bff";
        var otlpEndpoint = config["Telemetry:OtlpEndpoint"];
        var environment = config["Telemetry:Environment"]
                          ?? env.EnvironmentName;

        var resourceBuilder = ResourceBuilder.CreateDefault()
            .AddService(serviceName)
            .AddAttributes(new Dictionary<string, object>
            {
                ["capability_id"] = DashboardTelemetry.CapabilityId,
                ["zone"]          = DashboardTelemetry.Zone,
                ["deployable"]    = DashboardTelemetry.Deployable,
                ["environment"]   = environment,
            });

        services.AddOpenTelemetry()
            .WithTracing(tracing =>
            {
                tracing
                    .SetResourceBuilder(resourceBuilder)
                    .AddSource(DashboardTelemetry.SourceName)
                    .AddSource("MassTransit")
                    .AddAspNetCoreInstrumentation()
                    .AddHttpClientInstrumentation();

                if (!string.IsNullOrWhiteSpace(otlpEndpoint))
                {
                    tracing.AddOtlpExporter(o => o.Endpoint = new Uri(otlpEndpoint));
                }
                else
                {
                    tracing.AddConsoleExporter();
                }
            })
            .WithMetrics(metrics =>
            {
                metrics
                    .SetResourceBuilder(resourceBuilder)
                    .AddMeter(DashboardTelemetry.SourceName)
                    .AddAspNetCoreInstrumentation()
                    .AddRuntimeInstrumentation();

                if (!string.IsNullOrWhiteSpace(otlpEndpoint))
                {
                    metrics.AddOtlpExporter(o => o.Endpoint = new Uri(otlpEndpoint));
                }
            });

        return services;
    }
}
