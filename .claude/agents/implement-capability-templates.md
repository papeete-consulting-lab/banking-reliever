# Code Templates

> **Layout note.** All deployment templates below — `Dockerfile`, `docker-compose.yml`, `.env`, `platform.compose.yml`, and the deployment `README.md` — render to `sources/{capability-lower}/backend/deployment/local/`, **not** to the component root. The `svc/config/*.json` (`appsettings*.json`) files stay at their current location under `Presentation/`.

All placeholders: `{Namespace}`, `{CapabilityName}`, `{AggregateName}`, `{capability-lower}`, `{COMPONENT_PORT}`, `{channel}`.

---

## nuget.config

```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <clear />
    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />
    <add key="naive-unicorn" value="https://nuget.pkg.github.com/naive-unicorn/index.json" />
  </packageSources>
  <packageSourceCredentials>
    <naive-unicorn>
      <add key="Username" value="%GITHUB_USERNAME%" />
      <add key="ClearTextPassword" value="%GITHUB_TOKEN%" />
    </naive-unicorn>
  </packageSourceCredentials>
</configuration>
```

---

## deployment/local/docker-compose.yml

Component-only compose. RabbitMQ + MongoDB are NOT bundled here — they live
on the external `<product>-platform` Docker network and are reached by service
name (`rabbitmq`, `mongo`).

```yaml
services:
  {capability-lower}-api:
    image: {capability-lower}-api:dev
    build: .
    env_file: .env
    networks: [<product>-platform]
    ports: ["${COMPONENT_PORT}:8080"]
    healthcheck:
      test: ["CMD","curl","-fsS","http://localhost:8080/health"]
      interval: 10s
      retries: 6
networks:
  <product>-platform: { external: true }
```

---

## deployment/local/.env

```
COMPONENT_PORT={COMPONENT_PORT}
ASPNETCORE_ENVIRONMENT=Development
MongoDbConnection=mongodb://admin:password@mongo:27017/{capability-lower}?authSource=admin
RabbitMQConnection=amqp://admin:password@rabbitmq:5672/{capability-lower}
```

---

## deployment/local/platform.compose.yml

Opt-in stand-in platform for local dev / tests. Creates the external
`<product>-platform` network and stands up RabbitMQ + MongoDB on standard host
ports. Explicitly **not** the real platform — the component's own compose
never owns infra.

```yaml
# Stand-in platform for local dev / tests — NOT the real platform.
services:
  rabbitmq:
    image: rabbitmq:3.13-management-alpine
    ports: ["5672:5672", "15672:15672"]
    environment: { RABBITMQ_DEFAULT_USER: admin, RABBITMQ_DEFAULT_PASS: password }
    healthcheck: { test: ["CMD","rabbitmq-diagnostics","-q","ping"], interval: 10s, retries: 6 }
  mongo:
    image: mongo:7
    ports: ["27017:27017"]
    environment: { MONGO_INITDB_ROOT_USERNAME: admin, MONGO_INITDB_ROOT_PASSWORD: password }
    healthcheck: { test: ["CMD-SHELL","mongosh --quiet --eval 'db.runCommand({ping:1}).ok' | grep 1"], interval: 10s, retries: 6 }
networks:
  default:
    name: <product>-platform
    external: true
```

---

## svc/config/cold.json

```json
{
  "MongoDbConnection": "mongodb://admin:password@mongo:27017/{capability-lower}?authSource=admin",
  "AzureServiceBusEnabled": false,
  "RabbitMQEnabled": true,
  "RabbitMQConnection": "amqp://admin:password@rabbitmq:5672/{capability-lower}",
  "BusSerializationOptions": {
    "PropertyNamingPolicy": "CamelCase",
    "IncludeFields": false,
    "IgnoreNullValues": true
  },
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore": "Warning",
      "MongoDB.Driver.Core": "Warning"
    }
  }
}
```

## svc/config/hot.json

```json
{
  "Namespace": "Local",
  "ApplicationInsights": {
    "ConnectionString": ""
  },
  "ServiceBusConnectionString": "",
  "MongoDbConnection": "mongodb://admin:password@mongo:27017/{capability-lower}?authSource=admin",
  "RabbitMQConnection": "amqp://admin:password@rabbitmq:5672/{capability-lower}",
  "Port": 8080
}
```

---

## Project Files (.csproj)

### Contracts.csproj

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <RootNamespace>{Namespace}.{CapabilityName}.Contracts</RootNamespace>
    <AssemblyName>{Namespace}.{CapabilityName}.Contracts</AssemblyName>
    <PackageId>NaiveUnicorn.{Namespace}.{CapabilityName}.Contracts</PackageId>
    <Version>1.0.0</Version>
    <Authors>naive-unicorn</Authors>
    <Description>Shared contracts for the {Namespace} {CapabilityName} business capability</Description>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="NaiveUnicorn.Component.Messaging" Version="1.2.0" />
  </ItemGroup>
</Project>
```

### Domain.csproj

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="NaiveUnicorn.Component.Bus" Version="1.2.0" />
    <PackageReference Include="NaiveUnicorn.Component.DB" Version="1.2.0" />
    <PackageReference Include="NaiveUnicorn.Component.Logging" Version="1.2.0" />
    <ProjectReference Include="../{Namespace}.{CapabilityName}.Contracts/{Namespace}.{CapabilityName}.Contracts.csproj" />
  </ItemGroup>
</Project>
```

### Application.csproj

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="NaiveUnicorn.Component.Bus" Version="1.2.0" />
    <PackageReference Include="NaiveUnicorn.Component.DB" Version="1.2.0" />
    <PackageReference Include="NaiveUnicorn.Component.Logging" Version="1.2.0" />
    <ProjectReference Include="../{Namespace}.{CapabilityName}.Domain/{Namespace}.{CapabilityName}.Domain.csproj" />
    <ProjectReference Include="../{Namespace}.{CapabilityName}.Infrastructure/{Namespace}.{CapabilityName}.Infrastructure.csproj" />
    <ProjectReference Include="../{Namespace}.{CapabilityName}.Contracts/{Namespace}.{CapabilityName}.Contracts.csproj" />
  </ItemGroup>
</Project>
```

### Infrastructure.csproj

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="NaiveUnicorn.Component.DB.Mongo" Version="1.2.0" />
    <ProjectReference Include="../{Namespace}.{CapabilityName}.Domain/{Namespace}.{CapabilityName}.Domain.csproj" />
  </ItemGroup>
</Project>
```

### Presentation.csproj

```xml
<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <EnableDefaultContentItems>false</EnableDefaultContentItems>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Swashbuckle.AspNetCore" Version="7.0.0" />
    <PackageReference Include="NaiveUnicorn.Component.Bus" Version="1.2.0" />
    <PackageReference Include="NaiveUnicorn.Component.Correlation.Http" Version="1.2.0" />
    <PackageReference Include="NaiveUnicorn.Component.MessagePublisher" Version="1.2.0" />
    <PackageReference Include="NaiveUnicorn.Component.Reactor" Version="1.2.0" />
    <ProjectReference Include="../{Namespace}.{CapabilityName}.Application/{Namespace}.{CapabilityName}.Application.csproj" />
    <ProjectReference Include="../{Namespace}.{CapabilityName}.Domain/{Namespace}.{CapabilityName}.Domain.csproj" />
    <ProjectReference Include="../{Namespace}.{CapabilityName}.Infrastructure/{Namespace}.{CapabilityName}.Infrastructure.csproj" />
    <ProjectReference Include="../{Namespace}.{CapabilityName}.Contracts/{Namespace}.{CapabilityName}.Contracts.csproj" />
  </ItemGroup>
  <ItemGroup>
    <Content Include="Dockerfile" CopyToOutputDirectory="Never" CopyToPublishDirectory="Always" />
  </ItemGroup>
  <ItemGroup>
    <Content Include="config/cold.json" CopyToOutputDirectory="Always" CopyToPublishDirectory="Always">
      <CopyToOutputDirectory>Always</CopyToOutputDirectory>
    </Content>
    <Content Include="config/hot.json" CopyToOutputDirectory="Always" CopyToPublishDirectory="Never">
      <CopyToOutputDirectory>Always</CopyToOutputDirectory>
    </Content>
  </ItemGroup>
</Project>
```

---

## Contracts Layer

### Commands/Create{AggregateName}Command.cs

```csharp
namespace {Namespace}.{CapabilityName}.Contracts.Commands;

public record Create{AggregateName}Command(Guid Id);
```

### Events/{AggregateName}Created.cs

```csharp
using Foodaroo.Component.Messaging;

namespace {Namespace}.{CapabilityName}.Contracts.Events;

public class {AggregateName}Created : IMessage
{
    public Guid AggregateId { get; set; }
}
```

---

## Domain Layer

### Errors/Code.cs

```csharp
namespace {Namespace}.{CapabilityName}.Domain.Errors;

public static class Code
{
    public const string InvalidState = "INVALID_STATE";
    public const string NotFound = "NOT_FOUND";
}
```

### Model/AR/{AggregateName}/DTO/{AggregateName}Dto.cs

```csharp
using Foodaroo.Component.DB.Repository.Base;
using Foodaroo.Component.DB.Repository.Base.Interfaces;
using Foodaroo.Component.Messaging;

namespace {Namespace}.{CapabilityName}.Domain.Model.AR.{AggregateName};

[Collection(Name = "{AggregateName}")]
public class {AggregateName}Dto : IAggregateRootDto, IDbObject, IDbAggregate
{
    public long LastUpdateUnixTimestamp { get; set; }
    public Guid TechnicalId { get; set; }
    public int State { get; set; }
}
```

### Model/AR/{AggregateName}/{AggregateName}AR.cs

```csharp
using Foodaroo.Component.Domain.Aggregate;
using Foodaroo.Component.Domain.Exceptions;
using {Namespace}.{CapabilityName}.Contracts.Events;
using {Namespace}.{CapabilityName}.Domain.Errors;

namespace {Namespace}.{CapabilityName}.Domain.Model.AR.{AggregateName};

public class {AggregateName}AR : AggregateRoot<{AggregateName}Dto>
{
    private Guid _id;
    private {AggregateName}State _state;

    public enum {AggregateName}State
    {
        Created,
        Active,
        Closed
    }

    public {AggregateName}AR(Guid id)
    {
        if (id == Guid.Empty) throw new ArgumentNullException(nameof(id));
        _id = id;
        _state = {AggregateName}State.Created;
    }

    public {AggregateName}AR(Guid id, int state)
    {
        _id = id;
        _state = ({AggregateName}State)state;
    }

    public static {AggregateName}AR Create(Guid id)
    {
        var ar = new {AggregateName}AR(id);
        ar.RaiseEvent(new {AggregateName}Created { AggregateId = id });
        return ar;
    }

    public override {AggregateName}Dto ToDto(long lastUpdateUnixTimestamp) => new()
    {
        TechnicalId = _id,
        LastUpdateUnixTimestamp = lastUpdateUnixTimestamp,
        State = (int)_state
    };
}
```

### Model/AR/{AggregateName}/Factory/I{AggregateName}Factory.cs

```csharp
namespace {Namespace}.{CapabilityName}.Domain.Model.AR.{AggregateName};

public interface I{AggregateName}Factory
{
    {AggregateName}AR CreateInstance(Guid id);
    {AggregateName}AR CreateInstance({AggregateName}Dto payload);
}
```

### Model/AR/{AggregateName}/Factory/{AggregateName}Factory.cs

```csharp
namespace {Namespace}.{CapabilityName}.Domain.Model.AR.{AggregateName};

public class {AggregateName}Factory : I{AggregateName}Factory
{
    public {AggregateName}AR CreateInstance(Guid id)
        => new {AggregateName}AR(id);

    public {AggregateName}AR CreateInstance({AggregateName}Dto payload)
        => new {AggregateName}AR(payload.TechnicalId, payload.State);
}
```

---

## Infrastructure Layer

### Data/Domain/{AggregateName}MongoRepository.cs

```csharp
using Foodaroo.Component.DB.Repository.Base;
using Foodaroo.Component.DB.Repository.Base.Interfaces;
using Foodaroo.Component.DB.Repository.Mongo;
using Foodaroo.Component.Configuration;
using Foodaroo.Component.Logging;
using Foodaroo.Component.Messaging;
using Foodaroo.Component.Correlation;
using {Namespace}.{CapabilityName}.Domain.Model.AR.{AggregateName};

namespace {Namespace}.{CapabilityName}.Infrastructure.Data.Domain;

public interface IRepository{AggregateName}
{
    Task<{AggregateName}AR> GetByAggregateRootId(Guid id);
    Task SaveAggregate({AggregateName}AR aggregate);
    Task SaveAggregate({AggregateName}AR aggregate, IDbSession session);
    Task InsertAggregate({AggregateName}AR aggregate);
}

public class {AggregateName}MongoRepository
    : MongoAggregateRepositoryBase<{AggregateName}AR, {AggregateName}Dto>, IRepository{AggregateName}
{
    private readonly I{AggregateName}Factory _factory;
    private AggregateDocument<{AggregateName}Dto>? _currentDoc;

    public {AggregateName}MongoRepository(
        ITransactionHandler tranHandler,
        IMongoHandle<AggregateDocument<{AggregateName}Dto>> mongoHandle,
        IMongoHandle<DbMessage> mongoHandleEvt,
        ILogFoodaroo logger,
        ICorrelationContextAccessor correlation,
        DBSerializationOptions serializationOptions,
        EnvironmentSettings environment)
        : base(tranHandler, mongoHandle, mongoHandleEvt, logger, correlation, serializationOptions, environment)
    {
        _factory = new {AggregateName}Factory();
    }

    public async Task<{AggregateName}AR> GetByAggregateRootId(Guid id)
    {
        _currentDoc = await SingleAsync(m => m.Payload != null && m.Payload.TechnicalId == id);
        if (_currentDoc?.Payload == null)
            throw new InvalidOperationException($"Aggregate with id {id} not found");
        return _factory.CreateInstance(_currentDoc.Payload);
    }

    public async Task SaveAggregate({AggregateName}AR aggregate)
    {
        if (_currentDoc == null)
            await InsertAsync(aggregate);
        else
            await ReplaceAsync(_currentDoc, aggregate);
    }

    public async Task SaveAggregate({AggregateName}AR aggregate, IDbSession session)
    {
        if (_currentDoc == null)
            await InsertAsync(aggregate, session);
        else
            await ReplaceAsync(_currentDoc, aggregate, session);
    }

    public async Task InsertAggregate({AggregateName}AR aggregate)
        => await InsertAsync(aggregate);
}
```

---

## Application Layer

### Contract/{AggregateName}/ICreate{AggregateName}Service.cs

```csharp
using {Namespace}.{CapabilityName}.Contracts.Commands;

namespace {Namespace}.{CapabilityName}.Application.Contract.{AggregateName};

public interface ICreate{AggregateName}Service
{
    Task<Guid> CreateAsync(Create{AggregateName}Command command);
}
```

### Service/{AggregateName}/Create{AggregateName}Service.cs

```csharp
using Foodaroo.Component.Messaging;
using {Namespace}.{CapabilityName}.Application.Contract.{AggregateName};
using {Namespace}.{CapabilityName}.Contracts.Commands;
using {Namespace}.{CapabilityName}.Domain.Model.AR.{AggregateName};
using {Namespace}.{CapabilityName}.Infrastructure.Data.Domain;

namespace {Namespace}.{CapabilityName}.Application.Service.{AggregateName};

public class Create{AggregateName}Service : ICreate{AggregateName}Service
{
    private readonly IRepository{AggregateName} _repository;
    private readonly I{AggregateName}Factory _factory;
    private readonly IPublish _publisher;

    public Create{AggregateName}Service(
        IRepository{AggregateName} repository,
        I{AggregateName}Factory factory,
        IPublish publisher)
    {
        _repository = repository;
        _factory = factory;
        _publisher = publisher;
    }

    public async Task<Guid> CreateAsync(Create{AggregateName}Command command)
    {
        var id = command.Id == Guid.Empty ? Guid.NewGuid() : command.Id;
        var aggregate = {AggregateName}AR.Create(id);

        await _repository.InsertAggregate(aggregate);

        foreach (var evt in aggregate.GetDomainEvents())
            await _publisher.PublishAsync(evt, "{channel}");

        aggregate.ClearDomainEvents();
        return id;
    }
}
```

---

## Presentation Layer

### AppSettings.cs

```csharp
namespace {Namespace}.{CapabilityName}.Presentation;

public class AppSettings
{
    public string Namespace { get; set; } = string.Empty;
    public string ServiceBusConnectionString { get; set; } = string.Empty;
    public string MongoDbConnection { get; set; } = string.Empty;
    public string RabbitMQConnection { get; set; } = string.Empty;
    public int Port { get; set; }
}
```

### Program.cs

```csharp
using Foodaroo.Component.DependencyInjection;
using Foodaroo.Component.DB.Repository.Mongo;
using Foodaroo.Component.DB.Repository.Base.Interfaces;
using Foodaroo.Component.Configuration;
using Foodaroo.Component.BackgroundServices;
using Microsoft.OpenApi.Models;
using {Namespace}.{CapabilityName}.Application.Contract.{AggregateName};
using {Namespace}.{CapabilityName}.Application.Service.{AggregateName};
using {Namespace}.{CapabilityName}.Domain.Model.AR.{AggregateName};
using {Namespace}.{CapabilityName}.Infrastructure.Data.Domain;

var builder = WebApplication.CreateBuilder(args);

builder.Configuration.AddJsonFile("config/cold.json");
builder.Configuration.AddJsonFile("config/hot.json", true);

var envSettings = builder.Configuration.Get<EnvironmentSettings>();

if (envSettings?.Namespace == "Local")
    builder.WebHost.UseUrls("http://+:8080");
else
    builder.WebHost.UseUrls("http://*:8080");

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

builder.Services.AddComponentCorrelation();
builder.Services.AddHttpCorrelationPropagation();
builder.Services.AddComponentBus();
builder.Services.AddMongoLocker();
builder.Services.AddMessagePublishing();
builder.Services.AddComponentMongoRepositories();
builder.Services.AddComponentLogging();
builder.Services.AddComponentConfiguration();

builder.Services.AddHostedService<HostedMessagePublisherService>();

builder.Services.AddMongoAggregateRepository<IRepository{AggregateName}, {AggregateName}MongoRepository, {AggregateName}AR, {AggregateName}Dto>();
builder.Services.AddSingleton<ISessionFactory, MongoSessionFactory>();

builder.Services.AddTransient<I{AggregateName}Factory, {AggregateName}Factory>();
builder.Services.AddTransient<ICreate{AggregateName}Service, Create{AggregateName}Service>();
builder.Services.AddTransient<IRepository{AggregateName}, {AggregateName}MongoRepository>();

var app = builder.Build();

if (envSettings?.Namespace != "Prod")
{
    app.UseSwagger(c =>
    {
        c.PreSerializeFilters.Add((swaggerDoc, httpRequest) =>
        {
            if (!httpRequest.Headers.ContainsKey("X-Forwarded-Host")) return;
            var basePath = "{capability-lower}";
            var serverUrl = $"{httpRequest.Scheme}://{httpRequest.Headers["X-Forwarded-Host"]}/{basePath}";
            swaggerDoc.Servers = new List<OpenApiServer> { new OpenApiServer { Url = serverUrl } };
        });
    });
    app.UseSwaggerUI();
}

app.UseHttpCorrelationPropagation();
app.UseHttpsRedirection();
app.UseAuthorization();
app.MapControllers();

app.Run();
```

### Controllers/{AggregateName}CmdController.cs

```csharp
using Microsoft.AspNetCore.Mvc;
using Foodaroo.Component.Logging;
using {Namespace}.{CapabilityName}.Application.Contract.{AggregateName};
using {Namespace}.{CapabilityName}.Contracts.Commands;

namespace {Namespace}.{CapabilityName}.Presentation.Controllers;

[ApiController]
[Route("{AggregateName}")]
[Produces("application/json")]
public class {AggregateName}CmdController : ControllerBase
{
    [HttpPost]
    [Route("Create")]
    public async Task<IActionResult> Create(
        [FromBody] Create{AggregateName}Command cmd,
        [FromServices] ICreate{AggregateName}Service service)
    {
        var id = await service.CreateAsync(cmd);
        return Ok(id);
    }
}
```

### Controllers/{AggregateName}ReadController.cs

```csharp
using Microsoft.AspNetCore.Mvc;
using {Namespace}.{CapabilityName}.Infrastructure.Data.Domain;

namespace {Namespace}.{CapabilityName}.Presentation.Controllers;

[ApiController]
[Route("{AggregateName}")]
[Produces("application/json")]
public class {AggregateName}ReadController : ControllerBase
{
    [HttpGet]
    [Route("{id}")]
    public async Task<IActionResult> GetById(
        Guid id,
        [FromServices] IRepository{AggregateName} repository)
    {
        var aggregate = await repository.GetByAggregateRootId(id);
        return Ok(aggregate);
    }

    /// <summary>
    /// Health check — utilisé par test-business-capability pour attendre le démarrage du service.
    /// Retourne 200 OK quand le service est prêt à recevoir des requêtes.
    /// </summary>
    [HttpGet]
    [Route("/health")]
    public IActionResult Health() => Ok(new { status = "healthy", capability = "{capability-lower}" });
}
```

### Dockerfile

```dockerfile
FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS base
WORKDIR /app
EXPOSE 8080

FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY ["src/{Namespace}.{CapabilityName}.Presentation/{Namespace}.{CapabilityName}.Presentation.csproj", "src/{Namespace}.{CapabilityName}.Presentation/"]
COPY ["src/{Namespace}.{CapabilityName}.Application/{Namespace}.{CapabilityName}.Application.csproj", "src/{Namespace}.{CapabilityName}.Application/"]
COPY ["src/{Namespace}.{CapabilityName}.Domain/{Namespace}.{CapabilityName}.Domain.csproj", "src/{Namespace}.{CapabilityName}.Domain/"]
COPY ["src/{Namespace}.{CapabilityName}.Infrastructure/{Namespace}.{CapabilityName}.Infrastructure.csproj", "src/{Namespace}.{CapabilityName}.Infrastructure/"]
COPY ["src/{Namespace}.{CapabilityName}.Contracts/{Namespace}.{CapabilityName}.Contracts.csproj", "src/{Namespace}.{CapabilityName}.Contracts/"]
COPY ["nuget.config", "."]
RUN dotnet restore "src/{Namespace}.{CapabilityName}.Presentation/{Namespace}.{CapabilityName}.Presentation.csproj"
COPY . .
WORKDIR "/src/src/{Namespace}.{CapabilityName}.Presentation"
RUN dotnet build "{Namespace}.{CapabilityName}.Presentation.csproj" -c Release -o /app/build

FROM build AS publish
RUN dotnet publish "{Namespace}.{CapabilityName}.Presentation.csproj" -c Release -o /app/publish

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "{Namespace}.{CapabilityName}.Presentation.dll"]
```
