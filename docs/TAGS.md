# Tag Catalog (v2025-09-16)

This catalog defines canonical tags we attach to index records (`meta.tags`) to support boosted retrieval, filtering, and analytics. Tags reflect our current embedding and visual parsing capabilities (Canvas/Assessment/Diagram, Value Stack layers, Well-Architected pillars, diagram primitives, and core platform components).

Core Artifact Tags
- Canvas: Items derived from Platform Architecture Canvas.
- Assessment: Items derived from assessment/criteria artifacts.
- Diagram: Items representing structural diagrams or extracted entities.
- Table: Tabular artifacts (extracted or OCRed).
- Fallback: Facts synthesized from captions when structure is unknown.

Concept Tags
- Pillar: The Well‑Architected pillars domain is referenced.
- Layer: The Value Stack layers domain is referenced.

Value Stack Layers
- Engagement: User touchpoints and front‑line experiences.
- Intelligence: Analytics, ML/AI, decisioning.
- Infrastructure: Compute, storage, networking, core platforms.
- EcosystemConnectivity: Channels, APIs, edge/IoT connectivity.

Well‑Architected Pillars
- OperationalExcellence: Ops practices and operations as code.
- Security: Identity, IAM, encryption, protection-in-transit/at-rest.
- Reliability: Resilience, recovery, fault isolation.
- PerformanceEfficiency: Performance, scalability, right-sizing.
- CostOptimization: FinOps, cost efficiency, spend controls.

Process/Framework
- DoubleLoop, DiscoverAndLaunch, GrowthAndScale, DecisionGate, ValueStream, Principle,
- AssessmentBenchmark, Decision, WorkPackage, ControlPoint, BuyBuildPartnerJoin,
- EcosystemStrategyProcess, Needs, Vision, Offerings, Ventures, Initiate,
- FiveE, Ecosystemize, Explore, Embark, Embrace, Evolve,
- H1, H2, H3, EcosystemVenturePortfolio, PortfolioAlignment,
- FunctionalEcosystemIntegration, DecisionLog, ThreeP, People, Planet, Profit,
- Liquidity, NetworkEffects, Outcome, Goal.

Diagram/Visualization Primitives
- Persona, Role, Component, Service, System, Application,
- DataSource, Dataset, KPI, Metric, Criterion, Entity, Relation,
- Journey, Legend, Group, Node, Edge, Arrow, Swimlane, Timeline, Matrix, Heatmap,
- Region, BoundingBox.

Platform/Tech Components
- APIGateway, APIManagement, IdentityAndAccessManagement, Authentication, Authorization,
- DataPlatform, DataManagement, MachineLearning, Analytics, Streaming,
- DataLake, DataWarehouse, ETL, Orchestration, EventBus, Messaging,
- Caching, CDN, Observability, Monitoring, Logging, Tracing.

Notes
- Tags are case‑sensitive and must match these canonical forms.
- Retrieval applies `TAG_WEIGHTS` to multiply base scores. Example: `TAG_WEIGHTS=Canvas=1.06,Pillar=1.06,Layer=1.05,Assessment=1.05,Diagram=1.0`.
- Normalization injects tags during ingestion from region/page structures and fact metadata.
