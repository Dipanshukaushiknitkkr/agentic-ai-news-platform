# Agentic AI News Platform 🌐📰

An autonomous, multi-source technology news intelligence platform powered by FastAPI, PostgreSQL (Neon), Groq LLMs, and real-time story clustering.

---

## 🚀 Key Features

- **Autonomous Multi-Source Scraping**: Scrapes top tech publications (TechCrunch, The Verge, Ars Technica, Wired) on scheduled background intervals.
- **3-Layer Story Deduplication & Clustering**:
  - **Layer 1 (Copy Detector)**: MinHash LSH (128 permutations, adaptive shingling) detects exact & syndicated reprints without discarding articles.
  - **Layer 2 (Semantic Clusterer)**: Sentence Transformers (`all-MiniLM-L6-v2`) embeddings + 3-layer NER entity matching with 72h exponential time-decay.
  - **Layer 3 (LLM Verifier)**: Groq LLM verification with symmetric caching for borderline story pairings.
- **Fact-Checking & Contradiction Radar**:
  - Autonomous cross-source claim extraction with verbatim quote grounding.
  - Calculates mathematically bounded **Cross-Source Agreement Index (%)**.
  - Origin-aware attribution (direct investigation vs. official PR vs. anonymous leaks) detecting corporate PR echoes.
- **PostgreSQL / Neon Architecture**: Full production parity on Neon PostgreSQL with automated migration & schema sync.
- **Modern Responsive Glassmorphic UI**: Real-time story grouping ("Covered by N outlets"), filterable category feeds, admin console, and interactive contradiction audits.

---

## 🛠️ Tech Stack

- **Backend**: FastAPI, SQLAlchemy, APScheduler, Pydantic, Python-dotenv
- **NLP / ML**: Sentence-Transformers, Datasketch (MinHash LSH), spaCy (`en_core_web_sm`)
- **LLM Engine**: Groq API (multi-model fallback orchestration)
- **Database**: PostgreSQL (Neon Serverless with PgBouncer connection pooling)
- **Frontend**: Jinja2 Templates, Vanilla JavaScript, Tailwind CSS (CDN), FontAwesome

---

## 📦 Getting Started

### 1. Clone & Set Up Environment

```bash
git clone https://github.com/Dipanshukaushiknitkkr/agentic-ai-news-platform.git
cd agentic-ai-news-platform
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory (see `.env.example`):

```ini
GROQ_API_KEY=your_groq_api_key
DATABASE_URL=postgresql://user:password@host/neondb?sslmode=require
SECRET_KEY=your_secret_key
```

### 3. Run Application

```bash
python main.py
```

Visit `http://localhost:8000` in your browser.

---

## 🧪 Running Tests & Evaluation

```bash
# Run unit test suite
pytest tests/ -v

# Run deduplication evaluation benchmark
python eval/evaluate.py
python eval/benchmark.py
```
