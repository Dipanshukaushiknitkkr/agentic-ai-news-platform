from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
try:
    from backend.app.models import Base, Category, User
except ImportError:
    from app.models import Base, Category, User
import os

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tech_news.db")

# Force psycopg2 dialect for PostgreSQL (natively supports sslmode=require)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+psycopg2" not in DATABASE_URL and "+pg8000" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
elif "+pg8000" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("+pg8000", "+psycopg2", 1)

connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
pool_pre_ping = True if "sqlite" not in DATABASE_URL else False

engine = create_engine(
    DATABASE_URL, 
    connect_args=connect_args,
    pool_pre_ping=pool_pre_ping
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_database():
    """Initialize database and create default categories"""
    Base.metadata.create_all(bind=engine)
    
    # Auto-migration: Ensure columns exist
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE articles ADD COLUMN source VARCHAR DEFAULT 'TechNews'"))
            conn.commit()
    except Exception:
        pass
        
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
            conn.commit()
    except Exception:
        pass
        
    try:
        try:
            from backend.app.models import User
        except ImportError:
            from app.models import User
        db_admin = SessionLocal()
        admin_user = db_admin.query(User).filter(User.email == "18dkkaushik@gmail.com").first()
        if admin_user and not admin_user.is_admin:
            admin_user.is_admin = True
            db_admin.commit()
        db_admin.close()
    except Exception as e:
        print(f"Admin provisioning note: {e}")
    
    # Create or update default categories with rich 2026 taxonomy
    db = SessionLocal()
    try:
        default_categories = [
            {
                "name": "Artificial Intelligence",
                "description": "AI, machine learning, and automation news",
                "keywords": ["AI", "artificial intelligence", "machine learning", "ML", "neural network", "deep learning", "GPT", "LLM", "automation", "robot", "algorithm", "OpenAI", "ChatGPT", "Claude", "Anthropic", "Gemini", "DeepMind", "Nvidia", "Copilot", "reasoning", "model", "agent", "agentic", "Mistral", "Perplexity", "DeepSeek", "Midjourney", "GenAI", "generative AI", "diffusion", "inference", "prompt", "parameters", "transformer"]
            },
            {
                "name": "Startups & Funding",
                "description": "Startup news, funding rounds, and venture capital",
                "keywords": ["startup", "startups", "funding", "fund", "funds", "venture capital", "VC", "investment", "investments", "investor", "investors", "seed", "Series A", "Series B", "Series C", "IPO", "acquisition", "acquires", "acquired", "merger", "valuation", "raise", "raises", "raised", "raising", "Y Combinator", "accelerator", "unicorn", "angel", "backed", "capital", "shares", "finances", "founder", "founders", "pre-seed", "stealth", "round"]
            },
            {
                "name": "Big Tech",
                "description": "News from major technology companies",
                "keywords": ["Google", "Apple", "Microsoft", "Amazon", "Meta", "Facebook", "Tesla", "Netflix", "Uber", "Twitter", "X", "Alphabet", "Qualcomm", "Intel", "TSMC", "AMD", "YouTube", "AWS", "Azure", "Samsung", "Sony", "Oracle", "IBM", "ByteDance", "OpenAI", "Nvidia"]
            },
            {
                "name": "Cybersecurity",
                "description": "Security breaches, privacy, and cybersecurity news",
                "keywords": ["security", "breach", "hack", "hacker", "hackers", "cybersecurity", "privacy", "data protection", "vulnerability", "vulnerabilities", "malware", "ransomware", "encryption", "spyware", "phishing", "exploit", "exploits", "zero-day", "leaked", "leak", "passwords", "CVE", "FBI", "CISA", "security flaw", "patch", "infosec", "threat actor", "trojan", "botnet", "ransom"]
            },
            {
                "name": "Mobile & Apps",
                "description": "Mobile technology, apps, and smartphone news",
                "keywords": ["mobile", "smartphone", "smartphones", "app", "apps", "iOS", "Android", "iPhone", "iPhones", "Samsung", "tablet", "tablets", "wearable", "iPad", "MacBook", "Galaxy", "Pixel", "Snapdragon", "app store", "play store", "firmware", "handset", "foldable", "smartwatch", "AirPods", "Vision Pro", "device", "devices", "gadget", "gadgets"]
            },
            {
                "name": "Enterprise & SaaS",
                "description": "Enterprise software and SaaS solutions",
                "keywords": ["enterprise", "SaaS", "software", "cloud", "business", "productivity", "CRM", "ERP", "workflow", "collaboration", "database", "Snowflake", "Databricks", "Salesforce", "Kubernetes", "DevOps", "infrastructure", "B2B", "platform", "platforms", "API", "APIs", "microservices", "mainframe", "workplace", "analytics", "tools"]
            },
            {
                "name": "Electric Vehicles",
                "description": "Electric vehicles, autonomous driving, and transportation",
                "keywords": ["electric vehicle", "EV", "EVs", "autonomous", "self-driving", "Tesla", "transportation", "battery", "charging", "mobility", "Rivian", "Lucid", "BYD", "autopilot", "FSD", "Waymo", "Cruise", "supercharger", "NACS", "range", "gigafactory", "electric car", "robotaxi"]
            },
            {
                "name": "Fintech",
                "description": "Financial technology and digital payments",
                "keywords": ["fintech", "cryptocurrency", "bitcoin", "blockchain", "payment", "digital wallet", "banking", "financial", "crypto", "DeFi", "Stripe", "PayPal", "Revolut", "stablecoin", "SEC", "Ethereum", "wallet", "trading", "finance", "card", "debit", "credit", "ledger"]
            }
        ]
        
        for cat_data in default_categories:
            existing = db.query(Category).filter(Category.name == cat_data["name"]).first()
            if not existing:
                category = Category(**cat_data)
                db.add(category)
            else:
                existing.keywords = cat_data["keywords"]
                existing.description = cat_data["description"]
        
        db.commit()
        print("Updated category taxonomy with 2026 keywords")
    except Exception as e:
        print(f"Error initializing database categories: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_database()