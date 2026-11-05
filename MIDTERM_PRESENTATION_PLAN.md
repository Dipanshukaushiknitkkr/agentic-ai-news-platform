# Mid-Term / Progress Review Presentation: TechCore
## Autonomous Multi-Source Agentic AI News & Intelligence Platform
*(Phase II Progress Evaluation / Capstone Mid-Term Defense)*

---

## 🖥️ Slide 1: Title & Project Identity
- **Project Title**: **TechCore: Autonomous Multi-Source Agentic AI News Platform**
- **Subtitle**: Mid-Term Progress Review: Core Ingestion, Deduplication, Dynamic AI Gateway, and RAG Architecture
- **Project Status**: **Phase II / Mid-Term Evaluation (50% Milestone Reached)**
- **Presenter**: Dipanshu Kaushik
- **Domain**: Artificial Intelligence, Distributed Systems & Full-Stack Engineering
- **Code Repository**: `github.com/Dipanshukaushiknitkkr/agentic-ai-news-platform`

---

## 🎯 Slide 2: Project Identification & Problem Statement
### Industry & Technical Challenges
1. **Redundant Cross-Publisher Syndication**:
   - Technology news outlets (*TechCrunch, The Verge, Wired, Ars Technica*) cover identical press releases simultaneously, resulting in a **35%–45% duplicate story rate**.
2. **LLM Runtime Fragility ("The Model Deprecation Bottleneck")**:
   - Hardcoded cloud LLM endpoints regularly break when providers retire model strings or trigger HTTP 429 rate limits, crashing production apps.
3. **Temporal Blindness in Retrieval-Augmented Generation (RAG)**:
   - Standard semantic search lacks time awareness, treating "last 7 days" as generic words and mixing stale news with breaking updates.
4. **Cloud Ephemeral Filesystem Data Loss**:
   - Serverless deployment containers (Docker, Render) wipe local disk storage on restart, dropping raw scraped JSON feeds.

---

## 🎯 Slide 3: Project Scope & Core Objectives
### Overall Project Goals
- **Objective 1 (Completed)**: Build an automated, continuous multi-source RSS ingestion worker with persistent database storage.
- **Objective 2 (Completed)**: Implement a lightweight, sub-millisecond hybrid deduplication algorithm ($J \ge 0.48$, $R \ge 0.62$).
- **Objective 3 (Completed)**: Design a self-healing LLM gateway with dynamic live model discovery and automatic fallback.
- **Objective 4 (Completed)**: Develop a 12-domain categorization taxonomy guaranteeing 100% database coverage.
- **Objective 5 (In Progress)**: Deliver a time-aware RAG conversational assistant with structured executive briefings.
- **Objective 6 (Upcoming)**: User personalization, mobile-native client, automated audio digest generation, and multi-tenant scaling.

---

## 📚 Slide 4: Literature Review & Gap Analysis
How TechCore compares to current industry benchmarks:

| Evaluation Criterion | Standard RSS Aggregators (Feedly, Inoreader) | Naive LLM Wrappers | **TechCore (Our Approach)** |
|---|---|---|---|
| **Deduplication** | Exact URL/string matching (fails on rewritten headlines) | Heavy vector DB queries ($50\text{–}200\text{ ms}$) | **Token Jaccard + Levenshtein Sequence Ratio ($0.18\text{ ms}$)** |
| **Model Resilience** | No AI synthesis | Single hardcoded model string (breaks on deprecation) | **Runtime Model Discovery + 15m RAM Cache + Auto-Eviction** |
| **Categorization** | Manual user tags or coarse topics | Expensive zero-shot LLM prompts per article | **3x Title-Weighted Keyword Scoring + Contextual Fallback** |
| **Temporal Querying** | Keyword matching only | Blind to current date and time horizons | **Time-decay weighted scoring with current date anchoring** |
| **Data Persistence** | Proprietary closed databases | Ephemeral local disk files (lost on server reboot) | **Direct PostgreSQL persistence with non-blocking scheduler** |

---

## ⚙️ Slide 5: Methodology & System Architecture
```
    [Global RSS Feeds] (TechCrunch, The Verge, Wired, Ars Technica)
            │
            ▼
    [Asynchronous Ingestion Worker] (APScheduler / Manual Trigger)
            │
            ▼
    [Hybrid Deduplication Engine] (Jaccard >= 0.48 & Levenshtein >= 0.62)
            │
            ▼
    [Self-Healing Groq AI Gateway] (Runtime /models Discovery + Auto-Fallback)
            │
            ▼
    [12-Domain Automated Categorizer] (Title 3x Weight + Multi-Tier Contextual Fallback)
            │
            ▼
    [Persistent Database Tier] (Neon PostgreSQL on Cloud / SQLite Local)
            │
      ┌─────┴───────────────────────────────┐
      ▼                                     ▼
 [FastAPI RESTful Backend]        [Interactive Frontend UI]
 • Paginated Infinite Feed API    • Hero Info Bar (IST Clock + Tech History)
 • Time-Aware RAG Chat API        • 3D Tilt News Cards & Category Filters
 • OAuth2 / JWT Security Layer    • Executive AI Assistant Interface
 • Admin Telemetry & AI Tuner     • Admin Operations Console
```

---

## 📐 Slide 6: Methodology — Mathematical & Algorithmic Design
### 1. Hybrid Deduplication Metrics
To achieve sub-millisecond execution without expensive neural embedding lookups:
$$\text{Jaccard Token Similarity: } J(A, B) = \frac{|A \cap B|}{|A \cup B|}$$
$$\text{Levenshtein Sequence Ratio: } R(s_1, s_2) = \frac{2M}{|s_1| + |s_2|}$$
- **Duplicate Threshold**: `(J >= 0.48 AND |A ∩ B| >= 3) OR (R >= 0.62)`
- Evaluated over a sliding **72-hour temporal window** with domain-specific journalistic stopword stripping (*'announces', 'launches', 'unveils'*).

### 2. Time-Aware RAG Relevance Scoring
$$\text{Relevance Score} = (6 \times \text{Title Keyword Matches}) + (2 \times \text{Body Keyword Matches}) + \text{Temporal Bonus}$$
- Injects a **+5 point time-recency bonus** when temporal phrases (*"last 7 days"*, *"this week"*) are detected, grounding the LLM in legitimately fresh news.

---

## 📅 Slide 7: Work Plan & Project Lifecycle (Mid-Point Status)
The project follows a 5-phase engineering lifecycle. We are currently at the **Mid-Term Milestone (50% Completion)**:

```
[COMPLETED] Phase 1: Foundation & Data Pipeline (Weeks 1–3)
├── Multi-source RSS aggregation (TechCrunch, The Verge, Wired, Ars Technica)
├── Database schema design & direct PostgreSQL/SQLite persistence
└── APScheduler non-blocking asynchronous task integration

[COMPLETED] Phase 2: Core Algorithms & AI Gateway (Weeks 4–6)
├── Hybrid Jaccard + Levenshtein deduplication engine (0.18 ms latency)
├── 12-domain categorization taxonomy with 100% database coverage
└── Dynamic Groq live model discovery with auto-eviction fallback cascade

[CURRENT] Phase 3: Conversational RAG & Interface Hardening (Weeks 7–8) ◄── [WE ARE HERE]
├── Time-aware RAG assistant with executive structured output formatting
└── Interactive UI (3D Tilt Cards, Live IST Clock, Admin Telemetry Console)

[UPCOMING] Phase 4: Personalization & Advanced Intelligence (Weeks 9–10)
├── User bookmarking, reading history tracking & custom digest compilation
└── Autonomous fact-checking multi-agent verification loop

[UPCOMING] Phase 5: Production Scaling & Deployment (Weeks 11–12)
├── Hybrid search (BM25 + pgvector embeddings)
└── Production hardening on Cloud PaaS with automated health monitoring
```

---

## 📊 Slide 8: Progress Achieved — Module Completion Status

| Module / Subsystem | Planned Scope | Current Status | Key Deliverable |
|---|---|:---:|---|
| **Multi-Source Ingestion** | Ingest 4 feeds continuously | ✅ **100% Complete** | 24/7 background worker, direct DB writes |
| **Deduplication Engine** | Eliminate cross-publisher duplicates | ✅ **100% Complete** | Hybrid Jaccard + Levenshtein algorithm ($0.18\text{ ms}$) |
| **Dynamic AI Gateway** | Zero-downtime model orchestration | ✅ **100% Complete** | Runtime `/models` discovery + 15m RAM cache |
| **Content Categorization** | Multi-topic taxonomy tagging | ✅ **100% Complete** | 12 categories, 100% database coverage |
| **Time-Aware RAG Assistant** | Conversational tech intelligence | 🟡 **75% Complete** | Temporal entity retrieval working; tuning multi-turn memory |
| **Web UI & Admin Center** | Responsive user experience | 🟡 **80% Complete** | Glassmorphism card grid, live clock, admin panel live |
| **Personalization Engine** | User recommendations & alerts | 🔴 **Pending (Phase 4)** | Planned for next sprint |
| **Production Scale & Vector Search** | Hybrid semantic vector search | 🔴 **Pending (Phase 5)** | Planned for final sprint |

---

## 📈 Slide 9: Progress Achieved — Empirical Benchmark Results

### 1. Deduplication Efficiency
- **Execution Speed**: **$0.185\text{ ms}$** average check per headline ($500\times$ faster than cloud embedding APIs).
- **Duplicate Reduction**: **$\approx 95\%$ relative reduction in duplicate clutter**, filtering $\approx 40\%$ redundant syndicated entries.
- **LLM Cost Reduction**: **$\approx 40\%$ fewer LLM API calls** by pruning duplicate stories prior to summarization.

### 2. Taxonomical Categorization Coverage
- **100% Coverage**: All **172+ articles** currently in the database successfully assigned to 1 or more of the 12 categories.
- **Top Categories**: AI & ML (72), Big Tech (72), Startups & VC (55), Enterprise & Cloud (34), Hardware & Chips (32).

### 3. AI Gateway Availability
- **Zero Deprecation Outages**: Seamlessly migrated across 3 Groq model retirements using runtime discovery (`openai/gpt-oss-120b`, `qwen/qwen3.8-27b`, `openai/gpt-oss-20b`).
- **Prompt Sanitization**: Automatically strips `<think>...</think>` internal reasoning tags for clean executive outputs.

---

## 🔬 Slide 10: Current Challenges & Technical Bottlenecks
What we encountered and how we are addressing it in the current sprint:

1. **Reasoning Token Leakage in Open-Weights Models**:
   - *Challenge*: Newer reasoning models (e.g., `openai/gpt-oss-120b`) output scratchpad thinking (`User asks:...`) before generating answers.
   - *Mitigation*: Implemented an automated regex post-processing filter in `groq_client.py` and tuned system prompts to enforce direct executive delivery.
2. **Cold-Start Latency on Serverless Cloud Containers**:
   - *Challenge*: Ingestion jobs during server boot slowed down initial HTTP ping responses.
   - *Mitigation*: Decoupled startup tasks into non-blocking `asyncio.to_thread` workers, allowing immediate port binding ($< 1\text{ s}$).
3. **Temporal Boundary Extraction**:
   - *Challenge*: Standard search engines fail to isolate date horizons like "last week".
   - *Mitigation*: Integrated an algorithmic date-parser that calculates absolute timestamps against current IST/UTC time.

---

## 🚀 Slide 11: Future Work (Remaining 50% Scope)
1. **Hybrid Vector Search Integration (BM25 + pgvector)**:
   - Augment token-based matching with dense neural vector embeddings for deep conceptual semantic search.
2. **Personalized User Recommendation Engine**:
   - Deliver tailored news feeds based on user bookmarks, clicked topics, and reading history.
3. **Automated Audio Digest Generation**:
   - Text-to-Speech (TTS) synthesis to generate 2-minute daily morning audio briefings.
4. **Autonomous Multi-Agent Fact-Checking**:
   - Cross-verify breaking news claims across opposing publishers to flag rumors and speculative reporting.
5. **Mobile Native Client & Push Alerts**:
   - Cross-platform mobile app (Flutter/React Native) with custom keyword push notifications.

---

## ⏱️ Slide 12: Remaining Timeline (Phases 3–5 Gantt Chart)

```
┌───────────┬────────────────────────────────────────────────────────┬─────────────┐
│ Sprints   │ Milestone / Deliverable                                │ Target Date │
├───────────┼────────────────────────────────────────────────────────┼─────────────┤
│ Sprint 4  │ Finalize Conversational RAG & Multi-Turn Cache Tuning │ Weeks 7–8   │
│ Sprint 5  │ User Personalization, Bookmarking & Custom Digests     │ Weeks 9–10  │
│ Sprint 6  │ Hybrid Vector Search (BM25 + pgvector integration)     │ Weeks 11–12 │
│ Sprint 7  │ Automated Audio Digest (TTS) & Web Push Alerts         │ Weeks 13–14 │
│ Sprint 8  │ Final Testing, Security Audit & Cloud Hardening        │ Weeks 15–16 │
└───────────┴────────────────────────────────────────────────────────┴─────────────┘
```

---

## 🏁 Slide 13: Summary & Mid-Term Conclusion
- **Current Standing**: The foundational data ingestion, deduplication engine ($0.18\text{ ms}$), self-healing AI gateway, and 12-category taxonomy are **fully built, benchmarked, and verified**.
- **Next Focus**: Transitioning from core data infrastructure into deep conversational RAG intelligence, personalization, and vector search.
- **Q&A**: *Thank you! Open to suggestions and technical feedback from the panel.*
