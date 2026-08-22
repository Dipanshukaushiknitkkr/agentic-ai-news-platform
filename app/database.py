from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, Category
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
    
    # Auto-migration: Ensure source column exists on articles table
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE articles ADD COLUMN source VARCHAR DEFAULT 'TechNews'"))
            conn.commit()
    except Exception:
        pass  # Column already exists
    
    # Create default categories
    db = SessionLocal()
    try:
        # Check if categories already exist
        if db.query(Category).count() == 0:
            default_categories = [
                {
                    "name": "Artificial Intelligence",
                    "description": "AI, machine learning, and automation news",
                    "keywords": ["AI", "artificial intelligence", "machine learning", "ML", "neural network", "deep learning", "GPT", "LLM", "automation", "robot", "algorithm"]
                },
                {
                    "name": "Startups & Funding",
                    "description": "Startup news, funding rounds, and venture capital",
                    "keywords": ["startup", "funding", "venture capital", "VC", "investment", "seed", "Series A", "Series B", "IPO", "acquisition", "merger"]
                },
                {
                    "name": "Big Tech",
                    "description": "News from major technology companies",
                    "keywords": ["Google", "Apple", "Microsoft", "Amazon", "Meta", "Facebook", "Tesla", "Netflix", "Uber", "Twitter", "X"]
                },
                {
                    "name": "Cybersecurity",
                    "description": "Security breaches, privacy, and cybersecurity news",
                    "keywords": ["security", "breach", "hack", "cybersecurity", "privacy", "data protection", "vulnerability", "malware", "ransomware", "encryption"]
                },
                {
                    "name": "Mobile & Apps",
                    "description": "Mobile technology, apps, and smartphone news",
                    "keywords": ["mobile", "smartphone", "app", "iOS", "Android", "iPhone", "Samsung", "mobile app", "tablet", "wearable"]
                },
                {
                    "name": "Enterprise & SaaS",
                    "description": "Enterprise software and SaaS solutions",
                    "keywords": ["enterprise", "SaaS", "software", "cloud", "business", "productivity", "CRM", "ERP", "workflow", "collaboration"]
                },
                {
                    "name": "Gaming",
                    "description": "Video games, gaming platforms, and esports",
                    "keywords": ["gaming", "game", "esports", "PlayStation", "Xbox", "Nintendo", "Steam", "mobile gaming", "VR gaming", "console"]
                },
                {
                    "name": "Electric Vehicles",
                    "description": "Electric vehicles, autonomous driving, and transportation",
                    "keywords": ["electric vehicle", "EV", "autonomous", "self-driving", "Tesla", "transportation", "battery", "charging", "mobility"]
                },
                {
                    "name": "Fintech",
                    "description": "Financial technology and digital payments",
                    "keywords": ["fintech", "cryptocurrency", "bitcoin", "blockchain", "payment", "digital wallet", "banking", "financial", "crypto", "DeFi"]
                },
                {
                    "name": "Social Media",
                    "description": "Social media platforms and creator economy",
                    "keywords": ["social media", "TikTok", "Instagram", "Snapchat", "creator", "influencer", "content creator", "social platform", "viral"]
                }
            ]
            
            for cat_data in default_categories:
                category = Category(**cat_data)
                db.add(category)
            
            db.commit()
            print("Created default categories")
        else:
            print("Categories already exist")
    except Exception as e:
        print(f"Error initializing database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_database()