# PIK — Справочник смысловых групп и визуальных объектов (RAG + Канвасы)

Единый «markdown‑канвас» для осмысленной разметки материалов в платформенной методологии PIK: 24 смысловые группы тегов + 50 визуальных объектов. Язык — управленческий с привязкой к ArchiMate (Motivation, Strategy, Business, Application, Technology). Подходит для текстов и канвасов, обеспечивает консистентность RAG и быструю навигацию по портфелю артефактов.

---

## Правила применения и весов
**Шкала влияния:** Критичен = 1.0 · Высокий = 0.8 · Средний = 0.5 · Низкий = 0.3 · Контекст = 0.1.
- **По петлям:** Discover/Launch — приоритет Market/Need, MVP, Go‑to‑Market. Growth/Scale — приоритет Liquidity, NetworkEffects, Trust, Data, Partnerships.
- **По уровням:** L1 (Portfolio) ↔ L2 (Market) ↔ L3 (Platform). Поднимаем вес там, где принимается решение.
- **Sustainability‑надбавка:** За влияние на People/Planet/Profit или SDGs добавляем +0.1 к итоговому весу.
- **Зоны канвасов:** «Монетизация», «Сетевые эффекты», «Ликвидность» — повышающие коэффициенты.

Примечание по базовым весам визуальных объектов:
- Машиночитаемая карта базовых весов (50 объектов) хранится в `config/visual_objects_weights.yaml` и используется анализатором регионов.
- Канон слоёв Canvas (PVStack): `Experience, Interactions, Data, Infrastructure` — канонизация через `config/semantic_synonyms.yaml`.

---

## I. Смысловые группы тегов (24)

1) **Жизненный цикл (Double Loop)** — фаза работ и тип решений.  
_Примеры:_ DoubleLoop/Discover, DoubleLoop/Launch, DoubleLoop/Growth, DoubleLoop/Scale.

2) **3 уровня экосистемного мышления** — контекст L1–L3.  
_Примеры:_ Level/Portfolio(L1), Level/Market(L2), Level/Platform(L3).

3) **Роли экосистемы и стейкхолдеры** — «кто» создает/получает ценность.  
_Примеры:_ Role/Orchestrator, Role/Producer, Role/Partner(Enabler), Role/Consumer.

4) **Портфельные стратегии** — выбор «где играть».  
_Примеры:_ Portfolio/MarketExpansion, Portfolio/MarketIntegration, Portfolio/MarketFocus, Portfolio/RoleDominance.

5) **Рынок и контрольные точки** — внешняя среда и точки управления.  
_Примеры:_ Market/Trends, Market/ValuePools, Market/ControlPoints, Market/Competition, Market/Coopetition.

6) **Ценность и JTBD** — зачем пользователю, в чем УТП.  
_Примеры:_ Value/Proposition, JTBD/Core, PainPoints, Gains, UnfairAdvantage.

7) **Go‑to‑Market и каналы** — как выходим и растем.  
_Примеры:_ GTM/Strategy, GTM/PLG, GTM/SalesLed, GTM/Channel, Segmentation, Positioning.

8) **Монетизация и юнит‑экономика** — деньги и масштабируемость.  
_Примеры:_ Monetization/Model, Pricing, TakeRate, LTV, CAC, ARPU, Churn, Payback.

9) **Ликвидность и матчинг** — «живость» рынка на платформе.  
_Примеры:_ Liquidity/Supply, Liquidity/Demand, Onboarding, Activation, MatchQuality, TimeToMatch.

10) **Сетевые эффекты** — усилители роста.  
_Примеры:_ NFX/CrossSide, NFX/SameSide, NFX/Data, NFX/Reputation, NFX/Complementors.

11) **Сообщества и вовлечение** — рост через участников.  
_Примеры:_ Communities/Creators, Communities/Developers, UGC, Engagement/Loops, Advocacy.

12) **Доверие и управление** — правила игры и сигналы доверия.  
_Примеры:_ Trust/Signals, ReputationSystem, Policy/Governance, Moderation, Fairness, Transparency.

13) **Опыт и путь пользователя** — дизайн взаимодействий end‑to‑end.  
_Примеры:_ Experience/OnPlatform, Experience/CrossPlatform, Journey/Frictions, NPS, CSAT.

14) **Партнерства и оркестрация** — коопетиция и интеграции.  
_Примеры:_ Partnerships/Strategic, Partnerships/Program, Coopetition, Integration/Partners.

15) **Данные и Data Flywheel** — интеллект и продукт на данных.  
_Примеры:_ Data/Acquisition, Data/Activation, Data/Monetization, Flywheel/Learn→Improve→Value.

16) **Платформенный стек ценности и функциональная интеграция** — выравнивание по Value Stack и шагам пути.  
_Примеры:_ PVStack/Experience, PVStack/Interactions, PVStack/Data, PVStack/Infrastructure; FI/Horizontal(JourneyStep), FI/Vertical(Layer).

17) **Архитектура и инфраструктура (ArchiMate)** — стратегические сервисы платформы.  
_Примеры:_ Technology/PlatformService, Application/ApplicationService, Application/DataObject, Technology/Node.

18) **Расширение и интернационализация** — география и смежные рынки.  
_Примеры:_ Expansion/Geo, Expansion/Adjacency, Localization, Playbooks.

19) **Устойчивость и импакт (Sustainability by Design)** — 3P и SDGs на уровне решений.  
_Примеры:_ 3P/People, 3P/Planet, 3P/Profit, SDG/Selected(01–17), Circularity.

20) **Бизнес‑кейс и метрики** — экономическая логика и управление целями.  
_Примеры:_ BusinessCase, CostStructure, ProfitabilityHorizon, KPIs, OKRs, Milestones.

21) **Риски и соответствие** — ограничения и регуляторика.  
_Примеры:_ Risk/Regulatory, Risk/Privacy, Risk/PlatformAbuse, Constraint(ArchiMate).

22) **Команда, компетенции и операционная модель** — «кто и как делает».  
_Примеры:_ Team/CoreCompetencies, OperatingModel, Culture/Innovation, Org/Evolution.

23) **Инвестиции и финансирование** — источники и приоритеты капитала.  
_Примеры:_ Investors/Strategic, Funding/Seed‑Growth, CapitalAllocation, ROI/Thesis.

24) **Процессы и дорожные карты (5E + Ecosystem Strategy Process)** — управляемый путь изменений.  
_Примеры:_ 5E/Ecosystemize‑Explore‑Embark‑Embrace‑Evolve, Roadmap/3Horizons, MgmtAlignment, Buy‑Build‑Partner‑Join.

---

## II. Смысловые визуальные объекты (50)

**Контекст и стратегия**
1) **Визия платформы** — целевое состояние и амбиция. [ArchiMate: Motivation/Goal] [Теги: Motivation/Goal].
2) **Контрольная точка** — точка захвата стоимости/рычага. [Strategy/Capability] [Теги: Strategy/ControlPoint].
3) **Белое пространство** — незанятый участок ценности. [Strategy/Resource] [Теги: Strategy/WhiteSpace].
4) **Позиционирование** — место в умах клиентов. [Strategy/CourseOfAction] [Теги: GTM/Positioning].
5) **Где играть** — целевая арена/категория. [Strategy/Capability] [Теги: Portfolio/Positioning].
6) **Как побеждать** — стратегический прием. [Strategy/CourseOfAction] [Теги: Strategy/Differentiation].
7) **Роадмэп 3 горизонтов** — темп эволюции. [Strategy/CourseOfAction] [Теги: Roadmap/3Horizons].
8) **Build–Buy–Partner–Join** — портфельное решение. [Strategy/CourseOfAction] [Теги: Strategy/Build|Buy|Partner|Join].

**Рынок и портфель**
9) **Карта экосистемы** — роли и ценностные потоки. [Business/Role+Value] [Теги: Portfolio/Map].
10) **Пул ценности** — концентрация маржи/выручки. [Business/Value] [Теги: Market/ValuePools].
11) **Сегмент спроса** — когорта клиентов. [Business/Role] [Теги: Market/Segment].
12) **Кластер предложения** — типовой поставщик. [Business/Role] [Теги: Market/SupplyCluster].
13) **Матрица коопетиции** — конкуренция/сотрудничество. [Business/Collaboration] [Теги: Market/Coopetition].
14) **Соседние рынки** — смежные возможности. [Strategy/Capability] [Теги: Expansion/Adjacency].

**Ценность и продукт**
15) **JTBD‑ядро** — работа пользователя. [Motivation/Driver] [Теги: JTBD/Core].
16) **Ценностное предложение** — обещание ценности. [Business/Value] [Теги: Value/Proposition].
17) **Ключевой сценарий** — «подпись» платформы. [Business/Process] [Теги: Interaction/Core].
18) **Контур MVP** — минимальный комплект ценности. [Business/Service] [Теги: MVP/Scope].
19) **Модуль платформенного сервиса** — единица сервиса. [ApplicationService+BusinessService] [Теги: Platform/ServiceModule].
20) **Пакет стимулов** — экономика мотивации участников. [Business/Contract] [Теги: Incentives/Design].

**Платформенная механика**
21) **Матчинг‑контур** — логика сопоставления. [Business/Process] [Теги: Interactions/MatchQuality].
22) **Онбординг** — путь подключения сторон. [Business/Process] [Теги: Platform/Onboarding].
23) **Калитка качества** — входные критерии. [Motivation/Constraint] [Теги: Quality/Criteria].
24) **Рейтинг и отзывы** — петля доверия. [Business/Service] [Теги: Trust/Reputation].
25) **Правила и модерация** — политика поведения. [Motivation/Constraint] [Теги: Governance/Policy].
26) **Витрина/поиск** — поверхность «Find». [Business/Service] [Теги: Interaction/Find].
27) **Обмен** — ядро транзакции. [Business/Process] [Теги: Interaction/Exchange].
28) **Ко‑создание** — совместное создание ценности. [Business/Process] [Теги: Interaction/Co‑Create].
29) **Партнерская программа** — рамка для энэйблеров. [Business/Collaboration] [Теги: Partnerships/Program].
30) **Каталог интеграций** — точки присоединения партнёров. [ApplicationService] [Теги: Partnerships/Integration].
31) **Порог ликвидности** — минимальный живой рынок. [Business/Value] [Теги: Liquidity/Threshold].

**Рост и масштабирование**
32) **Growth‑loop** — замкнутый цикл роста. [Business/Process] [Теги: Growth/Loop].
33) **Воронка активации** — от визита к первой ценности. [Business/Process] [Теги: Activation/Funnel].
34) **Community‑flywheel** — контент и связи → рост. [Business/Process] [Теги: Communities/Flywheel].
35) **Карта сетевых эффектов** — типы NFX по сторонам. [Business/Value] [Теги: NFX/Map].
36) **Реферальный путь** — вирусный контур. [Business/Process] [Теги: Growth/Referral].
37) **«Лестницы» монетизации** — тарифы/ограничения. [Business/Value] [Теги: Pricing/Tiers].
38) **Трек гео‑экспансии** — приоритеты стран. [Strategy/CourseOfAction] [Теги: Expansion/Geo].

**Доверие, риски, управление**
39) **Набор сигналов доверия** — признаки качества/безопасности. [Motivation/Requirement] [Теги: Trust/Signals].
40) **Верификация партнера** — проверка участников. [Business/Process] [Теги: Governance/Verification].
41) **Риск‑матрица** — вероятность × воздействие. [Motivation/Constraint] [Теги: Risk/Matrix].
42) **Этическая хартия** — принципы by design. [Motivation/Principle] [Теги: Governance/Ethics].
43) **Прозрачность/отчетность** — публичные метрики правил. [Business/Service] [Теги: Governance/Transparency].

**Данные и аналитика**
44) **Data‑flywheel** — «использование → обучение → ценность». [Application/DataObject] [Теги: Data/Flywheel].
45) **Здоровье платформы** — LTV, CAC, churn и др. [Business/Value] [Теги: KPIs/PlatformHealth].
46) **Поведенческая сегментация** — кластеры по действиям. [Business/Role] [Теги: Segmentation/Behavioral].
47) **Когортная линза** — ретеншн по волнам времени. [Business/Value] [Теги: Analytics/Cohorts].

**Операции, организация, ресурсы**
48) **Операционная модель** — роли, процессы, ритмы. [Business/Process] [Теги: OperatingModel].
49) **Ключевые компетенции** — стратегические способности. [Strategy/Capability] [Теги: Team/CoreCompetencies].
50) **Согласование управления** — «стратегический проспект» решений. [Strategy/CourseOfAction] [Теги: MgmtAlignment].

---

## III. Маркировка канвасов (практика)
**Для каждого артефакта фиксируйте:**
- **CanvasName** (тип канваса PIK) и **Zone** (зона блока по петлям Double Loop).  
- **Role** (Consumer | Producer | Partner(Enabler) | Orchestrator).  
- **Integration**: Horizontal/Step=…; Vertical/Layer=… (для Functional Integration Map).  
- **Sustainability**: 3P=…; SDG=… (если релевантно).  
- **Вес**: примените шкалу и корректировки (по петле, уровню, зоне).

**Мини‑пример (визуальный артефакт):** «Platform Growth Engine»  
Tags → Canvas/PlatformGrowthEngine; Growth/Liquidity; NFX/Cross‑Side; Role/Orchestrator; Integration/Vertical:ValueStack=Interactions; 3P/Profit; SDG/09.  
Вес → +0.1 к Growth/NFX за принадлежность к петле масштабирования.

---

## IV. Контрольный список интеграции в RAG
- Синхронизируйте справочник с пайплайном индексации (тексты + изображения).  
- Поддерживайте словарь синонимов/лексических вариантов для ключевых групп и объектов.  
- Ведите версионирование: vMAJOR.MINOR.PATCH с changelog по группам/объектам.  
- Проводите ежемесячный «груминг» весов под фазы Double Loop и стратегические приоритеты.
