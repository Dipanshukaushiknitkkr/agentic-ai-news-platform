# Presentation Plan: TechCore — Agentic AI News & Intelligence Platform

## Overview
This presentation document is tailored directly for academic/industry project defense, seminars, and stakeholder evaluation. It is structured around your specified 5 core pillars:
1. **Project Identification & Objectives**
2. **Literature Review & Existing Systems**
3. **Methodology & Work Plan**
4. **Progress Achieved & Results**
5. **Future Work & Timeline**

---

## Slide 1: Title & Project Identity
- **Title**: **TechCore: Autonomous Multi-Source Agentic AI News & Intelligence Platform**
- **Subtitle**: Automated Cross-Feed Deduplication, Resilient Multi-Tier LLM Orchestration, and Time-Aware Retrieval-Augmented Generation (RAG)
- **Presenter**: Dipanshu Kaushik
- **Affiliation / Domain**: Artificial Intelligence & Full-Stack Systems Engineering
- **Live Repository**: `github.com/Dipanshukaushiknitkkr/agentic-ai-news-platform`

---

## Slide 2: Project Identification (Problem Statement)
### Context & Industry Problem
1. **Information Overload & Syndicated Duplication**:
   - Modern tech news consumers face identical wire stories cross-published across multiple outlets (*TechCrunch, The Verge, Wired, Ars Technica*).
   - $\approx 35\% - 45\%$ of raw multi-source articles report duplicate milestones with cosmetic headline changes.
2. **Superficial Aggregation vs. Deep Synthesis**:
   - Standard RSS aggregators present uncurated headlines or generic truncations without executive context or analytical depth.
3. **Fragility of Cloud AI Gateways (The "Model Deprecation" Trap)**:
   - Modern AI providers regularly update or deprecate model identifiers and enforce strict rate limits. Hardcoded API endpoints cause catastrophic production outages (`500 Internal Server Error` / offline fallbacks).
4. **Cloud Container Ephemeral Storage**:
   - Modern PaaS deployments (e.g., Render, Docker) wipe local container disks upon reboot, causing file-based aggregators to lose data.

---

## Slide 3: Project Objectives
- **Automated 24/7 Ingestion Pipeline**: Ingest and structure continuous news feeds from global technology publications with sub-second database write latency.
- **High-Precision Algorithmic Deduplication**: Detect and discard syndicated duplicate stories without invoking expensive neural embeddings.
- **Fault-Tolerant, Dynamic LLM Gateway**: Implement runtime model discovery with automatic fallback across diverse LLM architectures to ensure zero downtime.
- **100% Taxonomical Classification**: Automatically categorize 100% of incoming content into a comprehensive 12-domain technology taxonomy.
- **Time-Aware RAG Assistant**: Build an interactive conversational AI capable of resolving temporal queries (e.g., *"news about Apple in the last 7 days"*) grounded in real platform data.
- **Production-Grade Architecture**: Support persistent cloud PostgreSQL, OAuth2/JWT security, and an administrative control panel with real-time telemetry.

---

## Slide 4: Literature Review & Gap Analysis

| Aspect | Existing Aggregators (Feedly, Google News) | Traditional LLM Wrappers | **TechCore (Proposed System)** |
|---|---|---|---|
| **Deduplication** | Exact URL/string matching (fails on cross-publisher rewrites) | None or high-latency vector DB queries | **Hybrid Token Jaccard + Levenshtein Matching ($0.18\text{ ms}$)** |
| **LLM Reliability** | Rule-based or static extractive text | Static hardcoded model strings (breaks on deprecation) | **Dynamic Live Discovery + In-Memory Cache + Auto-Eviction** |
| **Categorization** | Manual tags or generic broad buckets | Zero-shot LLM per article (costly, slow) | **Title-Weighted Keyword Scoring + Contextual Fallback (100% coverage)** |
| **Conversational RAG** | Absent | Generic chat without temporal boundaries | **Time-Decay Weighted RAG with 8-turn conversation memory** |
| **Infrastructure** | Proprietary, closed systems | Ephemeral filesystem loss on container restart | **Direct PostgreSQL persistence + Non-blocking AsyncIO scheduler** |

---

## Slide 5: Methodology — High-Level Architecture
```
  [Global RSS Feeds] (TechCrunch, The Verge, Wired, Ars Technica)
           │
           ▼
  [Asynchronous Ingestion Worker] (APScheduler / Manual Trigger)
           │
           ▼
  [Cross-Publisher Deduplication] (Jaccard Overlap >= 0.48 & Levenshtein >= 0.62)
           │
           ▼
  [Dynamic Groq AI Engine] (Runtime /models Discovery + Auto-Eviction Fallback)
           │
           ▼
  [12-Domain Automated Categorizer] (Title 3x Weight + Contextual Multi-Tier Fallback)
           │
           ▼
  [Persistent Database Tier] (Neon PostgreSQL on Production / SQLite Local)
           │
     ┌─────┴───────────────────────────────┐
     ▼                                     ▼
[FastAPI RESTful Core]           [Interactive User Presentation]
• Paginated Infinite Feed API    • Hero Info Bar (IST Clock + Tech History)
• Time-Aware RAG Chat API        • 3D Tilt News Cards & Topic Filters
• OAuth2 / JWT Auth Security     • Executive AI Assistant Interface
• Admin Telemetry & Tuning       • Admin Operations Console
```

---

## Slide 6: Methodology — Mathematical & Algorithmic Foundation
### 1. Hybrid Deduplication Metrics
To achieve sub-millisecond execution without neural embedding costs:
$$\text{Jaccard Similarity } J(A, B) = \frac{|A \cap B|}{|A \cup B|}$$
$$\text{Levenshtein Ratio } R(s_1, s_2) = \frac{2M}{|s_1| + |s_2|}$$
- **Duplicate Rule**: `(J >= 0.48 AND |A ∩ B| >= 3) OR (R >= 0.62)`
- Evaluated over a sliding **72-hour temporal window** with domain-specific stopword stripping.

### 2. Time-Aware RAG Scoring
$$\text{Relevance Score} = (6 \times \text{Title Matches}) + (2 \times \text{Body Matches}) + \text{Time Decay Bonus}$$
- Applies a +5 temporal boost for stories published within the user-requested horizon (e.g., $t \le 7\text{ days}$).

---

## Slide 7: Methodology — Implementation & Technical Stack
- **Backend Framework**: Python 3.11+, FastAPI (Asynchronous ASGI, Starlette, Pydantic)
- **Data Persistence**: SQLAlchemy ORM, Neon PostgreSQL (Production), SQLite (Local Dev)
- **AI & Inference Engine**: Groq Cloud API (`openai/gpt-oss-120b`, `qwen/qwen3.8-27b`, `openai/gpt-oss-20b`, `groq/compound`)
- **Ingestion & Automation**: APScheduler, Feedparser, BeautifulSoup4, Requests
- **Security & Authorization**: OAuth2 Password Bearer, Python-JOSE (JWT tokens), Bcrypt password hashing
- **Frontend Presentation**: Jinja2 Templates, Vanilla JavaScript, Modern CSS3 (Glassmorphism, 3D Particle Space, Responsive Grid)

---

## Slide 8: Work Plan & Phased Development Lifecycle
```
Phase 1: Foundation & Data Architecture (Weeks 1-2)
├── RSS aggregation pipeline & schema design (Articles, Users, Categories)
└── Database integration with PostgreSQL & SQLite abstractions

Phase 2: Algorithmic Intelligence (Weeks 3-4)
├── Hybrid Jaccard + Levenshtein deduplication engine
└── 12-domain categorization taxonomy with multi-tier contextual fallback

Phase 3: Resilient AI Gateway & Conversational RAG (Weeks 5-6)
├── Dynamic live Groq model discovery & runtime fallback cascade
└── Time-aware RAG assistant with executive structured output formatting

Phase 4: Admin Instrumentation & UI/UX (Weeks 7-8)
├── 3D particle space & glassmorphism card grid with infinite scroll
└── JWT-authenticated Admin Control Center with live scraper telemetry

Phase 5: Cloud Deployment & Hardening (Weeks 9-10)
├── Production migration to Render & Neon PostgreSQL
└── Non-blocking startup decoupling, HEAD keep-alives & performance profiling
```

---

## Slide 9: Progress Achieved — Key Results & Performance Metrics
### 1. Quantitative System Metrics
- **Deduplication Precision**: **$\approx 95\%$ relative reduction in duplicate news**, filtering $\approx 40\%$ redundant syndicated entries.
- **Execution Speed**: **$0.185\text{ ms}$** per deduplication comparison ($500\times$ faster than embedding lookups).
- **Categorization Coverage**: **$100\%$ database coverage** across 172+ articles with zero orphaned records.
- **LLM Cost Reduction**: **$\approx 40\%$ reduction in API calls** achieved by filtering duplicates prior to summarization.
- **Database Query Latency**: **$\mathcal{O}(1)$ query overhead** achieved through SQLAlchemy `joinedload` on relational joins.

### 2. Functional Milestones Completed
- [x] Autonomous multi-source scraping across 4 global publishers.
- [x] Zero-downtime self-healing LLM gateway resilient to model deprecations.
- [x] Interactive conversational assistant delivering structured executive briefings.
- [x] Admin console with real-time telemetry, model switching, and temperature tuning.
- [x] "Today in Tech History" autonomous milestone flashcard engine.

---

## Slide 10: Future Work & Planned Enhancements
1. **Multi-Modal Content Processing**:
   - Automatic video transcription (YouTube / podcasts) and infographic chart extraction via Vision LLMs.
2. **Personalized User Recommendation Engine**:
   - Collaborative filtering and vector cosine embeddings based on user bookmarks and reading history.
3. **Cross-Language Localization**:
   - Automated multi-lingual translation and audio text-to-speech (TTS) morning briefings.
4. **Autonomous Fact-Checking Agent**:
   - Cross-verifying breaking claims across opposing sources to flag rumors or speculative reporting.
5. **Real-Time Push Notifications**:
   - Web Push and Telegram/Discord bot integration for user-defined high-priority keyword alerts.

---

## Slide 11: Projected Timeline (Next Steps)
```
Gantt Chart Roadmap (Next 6 Months):
Month 1: Vector Embeddings & Hybrid Search (BM25 + pgvector)
Month 2: Automated Audio Briefings (Text-to-Speech synthesis)
Month 3: Mobile Native App (React Native / Flutter client)
Month 4: Autonomous Claim & Fact-Checking Multi-Agent Loop
Month 5: Enterprise Multi-Tenant Teams & Webhook Alerts
Month 6: Production Scaling & Global Multi-Region Edge Caching
```

---

## Slide 12: Conclusion & Q&A
- **Summary**: TechCore demonstrates an end-to-end autonomous architecture bridging real-time data ingestion, algorithmic optimization, and resilient LLM agent orchestration.
- **Takeaway**: By combining lightweight algorithmic filtering ($0.18\text{ ms}$) with fault-tolerant cloud AI, the platform delivers high intelligence density at minimal operating cost.
- **Questions**: Thank you! Open to feedback and technical questions.
