from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import timedelta
import os
import json
import re
import requests

# Import new modules
from app.database import get_db, init_database
from app.auth import authenticate_user, create_access_token, get_current_active_user, get_current_admin_user, create_user, get_user_by_email, ACCESS_TOKEN_EXPIRE_MINUTES
from app.models import User, Category, Article, ArticleCategory, UserSubscription, DigestLog
from app.schemas import *
from services.digest_service import digest_service
from services.categorization_service import categorizer
from scrapers.techcrunch import fetch_and_save_techcrunch_articles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Tech News Digest API", description="Personalized tech news digests and notifications")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

@app.get("/ping")
@app.get("/health")
def health_check():
    """Lightweight health check endpoint for keep-alive pingers"""
    return {"status": "ok", "message": "Server active"}

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

def scheduled_news_scrape_job():
    try:
        print("[SCHEDULER] Running background TechCrunch scrape & sync...")
        fetch_and_save_techcrunch_articles()
        categorizer.sync_articles_from_files()
        categorizer.cleanup_old_articles(days=7)
    except Exception as e:
        print(f"[SCHEDULER ERROR]: {e}")

# Initialize database and background scheduler on startup
@app.on_event("startup")
async def startup_event():
    init_database()
    # Initial scrape on startup
    scheduled_news_scrape_job()
    # Schedule hourly background news scraping
    if not scheduler.running:
        scheduler.add_job(scheduled_news_scrape_job, 'interval', hours=1, id='hourly_news_scrape', replace_existing=True)
        scheduler.start()
        print("[SCHEDULER] Background news scraper running 24/7 every 1 hour.")

SUMMARIES_DIR = 'data/summaries/'
PLACEHOLDER_IMAGE = 'https://images.unsplash.com/photo-1518770660439-4636190af475?w=600&auto=format&fit=crop&q=60'


# Helper: Get LLM answer from Groq

def get_llm_answer_groq(question, articles, history=None):
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY")
    
    use_fallback = False
    fallback_reason = ""
    
    if not api_key:
        use_fallback = True
        fallback_reason = "Groq API key not set in your .env file"
        
    if not use_fallback:
        # Compose context from top 5 articles (title + llm_summary)
        context = "\n\n".join([
            f"Title: {a['title']}\nAI Summary: {a.get('llm_summary','')}" for a in articles[:5]
        ])
        
        system_instruction = (
            "You are an expert AI Tech Assistant, company advisor, and news expert.\n"
            "Here is the recent tech news context retrieved from our database:\n"
            f"{context}\n\n"
            "Instructions:\n"
            "1. Use the retrieved tech news above as primary evidence for real-time news questions.\n"
            "2. Answer follow-up questions, general knowledge cross-questions, and background details about companies, founders, history, or technology seamlessly using your general knowledge.\n"
            "3. Maintain full conversation context with the user across follow-up questions.\n"
            "4. Provide a clear, well-formatted response using bullet points and clean paragraph line breaks. Avoid single-line compressed tables."
        )
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        messages = [{"role": "system", "content": system_instruction}]
        
        # Append conversation history turns
        if history and isinstance(history, list):
            for turn in history[-8:]:  # Keep up to 4 conversation turns (8 messages)
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if role in ["user", "assistant"] and content:
                    messages.append({"role": role, "content": content})
                    
        # Append current user question
        messages.append({"role": "user", "content": question})
        
        payload = {
            "model": "openai/gpt-oss-120b",
            "max_tokens": 400,
            "temperature": 0.7,
            "messages": messages
        }
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"Groq API connection error: {e}")
            use_fallback = True
            fallback_reason = "Outbound connection to Groq blocked, offline, or key invalid"
            
    if use_fallback:
        # Fallback offline semantic search logic
        if not articles:
            return f"[{fallback_reason}]\n\nI couldn't find any articles in my database to help answer your question."
        
        response_text = f"🤖 [OFFLINE FALLBACK MODE: {fallback_reason}]\n\nBased on your question, here are the most relevant articles found in my database:\n"
        for idx, a in enumerate(articles[:3], 1):
            sum_text = a.get('llm_summary') or a.get('summary', '')[:150] + '...'
            response_text += f"\n👉 {idx}. {a['title']}\n   {sum_text}\n"
        return response_text

def get_keywords(text):
    # Simple keyword extraction: split on non-word chars, lowercase, remove stopwords
    stopwords = set(['the','is','at','which','on','a','an','and','or','for','to','of','in','with','by','as','from','that','this','it','are','be','was','were','has','had','have','but','not','if','then','so','do','does','did','can','will','just','about','into','over','after','before','more','less','than','up','out','off','no','yes','you','i','we','they','he','she','his','her','their','our','my','your'])
    words = re.findall(r'\w+', text.lower())
    return [w for w in words if w not in stopwords and len(w) > 2]

def select_relevant_articles(question, articles, top_n=5):
    q_keywords = set(get_keywords(question))
    scored = []
    for a in articles:
        text = f"{a.get('title','')} {a.get('summary','')} {a.get('llm_summary','')}"
        a_keywords = set(get_keywords(text))
        score = len(q_keywords & a_keywords)
        scored.append((score, a))
    scored.sort(reverse=True, key=lambda x: x[0])
    # If all scores are zero, fallback to most recent
    if scored and scored[0][0] == 0:
        return articles[:top_n]
    return [a for score, a in scored[:top_n]]

@app.post("/auth/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    try:
        user = create_user(db, user_data.email, user_data.password, user_data.full_name)
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/token", response_model=Token)
async def login(request: Request, db: Session = Depends(get_db)):
    """Login and get access token - supports Form Data, JSON payloads, email, and username fields"""
    username = None
    password = None
    
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
            username = body.get("username") or body.get("email")
            password = body.get("password")
        except Exception:
            pass
    else:
        try:
            form = await request.form()
            username = form.get("username") or form.get("email")
            password = form.get("password")
        except Exception:
            pass

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing username/email or password"
        )

    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/auth/google")
async def google_login(request: Request, db: Session = Depends(get_db)):
    """Authenticate user with Google OAuth2 ID Token"""
    data = await request.json()
    id_token = data.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="Missing Google ID token")
        
    try:
        resp = requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}", timeout=10)
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Google token")
            
        payload = resp.json()
        email = payload.get("email")
        full_name = payload.get("name") or payload.get("given_name", "Google User")
        
        if not email:
            raise HTTPException(status_code=400, detail="Google token missing email")
            
        user = get_user_by_email(db, email)
        if not user:
            import uuid
            random_password = str(uuid.uuid4())
            user = create_user(db, email, random_password, full_name)
            
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google authentication failed: {str(e)}")

@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user information"""
    return current_user

# Category endpoints
@app.get("/categories", response_model=List[CategoryResponse])
async def get_categories(db: Session = Depends(get_db)):
    """Get all available categories"""
    categories = db.query(Category).all()
    return categories

# User preferences endpoints
@app.get("/preferences", response_model=DigestPreferences)
async def get_preferences(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Get user's digest preferences"""
    user_category_ids = [cat.id for cat in current_user.interests]
    return DigestPreferences(
        daily_digest_enabled=current_user.daily_digest_enabled,
        weekly_digest_enabled=current_user.weekly_digest_enabled,
        instant_notifications=current_user.instant_notifications,
        digest_time=current_user.digest_time,
        time_zone=current_user.time_zone,
        interested_categories=user_category_ids
    )

@app.put("/preferences", response_model=UserResponse)
async def update_preferences(
    preferences: PreferencesUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update user's digest preferences"""
    
    # Update basic preferences
    if preferences.daily_digest_enabled is not None:
        current_user.daily_digest_enabled = preferences.daily_digest_enabled
    if preferences.weekly_digest_enabled is not None:
        current_user.weekly_digest_enabled = preferences.weekly_digest_enabled
    if preferences.instant_notifications is not None:
        current_user.instant_notifications = preferences.instant_notifications
    if preferences.digest_time is not None:
        current_user.digest_time = preferences.digest_time
    if preferences.time_zone is not None:
        current_user.time_zone = preferences.time_zone
    
    # Update interested categories
    if preferences.interested_categories is not None:
        # Clear existing interests
        current_user.interests.clear()
        # Add new interests
        for category_id in preferences.interested_categories:
            category = db.query(Category).filter(Category.id == category_id).first()
            if category:
                current_user.interests.append(category)
    
    db.commit()
    db.refresh(current_user)
    return current_user

# Subscription endpoints
@app.post("/subscriptions", response_model=SubscriptionResponse)
async def create_subscription(
    subscription: SubscriptionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new subscription"""
    db_subscription = UserSubscription(
        user_id=current_user.id,
        subscription_type=subscription.subscription_type,
        category_id=subscription.category_id,
        keywords=subscription.keywords
    )
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription

@app.get("/subscriptions", response_model=List[SubscriptionResponse])
async def get_subscriptions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's subscriptions"""
    return current_user.subscriptions

@app.delete("/subscriptions/{subscription_id}")
async def delete_subscription(
    subscription_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a subscription"""
    subscription = db.query(UserSubscription).filter(
        UserSubscription.id == subscription_id,
        UserSubscription.user_id == current_user.id
    ).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    db.delete(subscription)
    db.commit()
    return {"message": "Subscription deleted"}

# Digest endpoints
@app.get("/digest/preview", response_model=DigestPreview)
async def preview_digest(
    digest_type: str = "daily",
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Preview digest content for the user"""
    days_back = 1 if digest_type == "daily" else 7
    max_articles = 5 if digest_type == "daily" else 10
    
    articles_by_category = digest_service.get_articles_for_user(
        db, current_user, days_back, max_articles
    )
    
    total_articles = sum(len(articles) for articles in articles_by_category.values())
    
    return DigestPreview(
        total_articles=total_articles,
        categories=articles_by_category,
        digest_type=digest_type
    )

@app.post("/digest/send")
async def send_digest_now(
    digest_type: str = "daily",
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Send digest immediately to the current user"""
    if digest_type == "daily":
        success = digest_service.generate_daily_digest(db, current_user, ignore_schedule=True)
    else:
        success = digest_service.generate_weekly_digest(db, current_user, ignore_schedule=True)
    
    if success:
        return {"message": f"{digest_type.title()} digest sent successfully"}
    else:
        raise HTTPException(status_code=400, detail="Failed to send digest")

@app.get("/digest/history", response_model=List[DigestLogResponse])
async def get_digest_history(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's digest history"""
    digest_logs = (db.query(DigestLog)
                   .filter(DigestLog.user_id == current_user.id)
                   .order_by(DigestLog.sent_at.desc())
                   .limit(20)
                   .all())
    return digest_logs

# Articles endpoints
@app.get("/articles", response_model=List[ArticleResponse])
async def get_articles(
    category_id: Optional[int] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get articles, optionally filtered by category"""
    query = db.query(Article)
    
    if category_id:
        query = query.join(ArticleCategory).filter(ArticleCategory.category_id == category_id)
    
    articles = query.order_by(Article.created_at.desc()).limit(limit).all()
    return articles

@app.get("/articles/personalized", response_model=List[ArticleResponse])
async def get_personalized_articles(
    current_user: User = Depends(get_current_active_user),
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get personalized articles for the current user"""
    articles_by_category = digest_service.get_articles_for_user(db, current_user, days_back=7, max_articles_per_category=limit//3)
    
    # Flatten the articles
    all_articles = []
    for articles in articles_by_category.values():
        all_articles.extend(articles)
    
    # Remove duplicates and sort by creation date
    seen = set()
    unique_articles = []
    for article in sorted(all_articles, key=lambda x: x.created_at, reverse=True):
        if article.id not in seen:
            seen.add(article.id)
            unique_articles.append(article)
    
    return unique_articles[:limit]

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the user dashboard for managing digest preferences"""
    return templates.TemplateResponse(request=request, name="dashboard.html", context={})

from datetime import timezone, timedelta

IST_TZ = timezone(timedelta(hours=5, minutes=30))

def format_published_ist(pub_str, created_at_dt=None):
    """Convert publication date or created_at timestamp to IST string (e.g. 23 Aug, 02:42 AM IST)"""
    dt = None
    if pub_str:
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(pub_str)
        except Exception:
            pass
            
    if not dt and created_at_dt:
        dt = created_at_dt.replace(tzinfo=timezone.utc)
        
    if not dt:
        dt = datetime.now(timezone.utc)
        
    # Convert to IST (UTC+5:30)
    ist_dt = dt.astimezone(IST_TZ)
    return ist_dt.strftime("%d %b, %I:%M %p IST")

@app.get('/', response_class=HTMLResponse)
def read_cards(request: Request, db: Session = Depends(get_db)):
    db_articles = db.query(Article).order_by(Article.created_at.desc()).all()
    if not db_articles:
        categorizer.sync_articles_from_files()
        db_articles = db.query(Article).order_by(Article.created_at.desc()).all()
    if not db_articles:
        try:
            fetch_and_save_techcrunch_articles()
            categorizer.sync_articles_from_files()
            db_articles = db.query(Article).order_by(Article.created_at.desc()).all()
        except Exception as e:
            print(f"Fallback article fetch failed: {e}")
            
    articles = []
    for art in db_articles:
        articles.append({
            'title': art.title,
            'link': art.link,
            'summary': art.summary or '',
            'llm_summary': art.llm_summary or '',
            'published': format_published_ist(art.published, art.created_at),
            'image_url': art.image_url or PLACEHOLDER_IMAGE,
            'source': getattr(art, 'source', 'TechNews') or 'TechNews',
            'categories': [ac.category for ac in art.categories if ac.category]
        })
    return templates.TemplateResponse(request=request, name="index.html", context={"articles": articles})

@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    return templates.TemplateResponse(request=request, name="chat.html", context={})

@app.post('/chat')
async def chat_endpoint(request: Request):
    data = await request.json()
    question = data.get('question', '')
    history = data.get('history', [])
    
    # Load all articles
    articles = []
    if os.path.exists(SUMMARIES_DIR):
        for filename in sorted(os.listdir(SUMMARIES_DIR), reverse=True):
            if filename.endswith('.json'):
                with open(os.path.join(SUMMARIES_DIR, filename), 'r', encoding='utf-8') as f:
                    article = json.load(f)
                articles.append(article)
                
    # Combine question with previous user message for search context
    search_query = question
    if history and isinstance(history, list):
        user_turns = [h.get('content', '') for h in history if h.get('role') == 'user']
        if user_turns:
            search_query = f"{user_turns[-1]} {question}"
            
    relevant_articles = select_relevant_articles(search_query, articles, top_n=5)
    answer = get_llm_answer_groq(question, relevant_articles, history=history)
    return JSONResponse({"answer": answer})

# Admin Control Panel Endpoints
@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    """Serve the Admin Control Panel"""
    return templates.TemplateResponse(request=request, name="admin.html", context={})

@app.get("/api/admin/stats")
async def get_admin_stats(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    """Get live admin system statistics"""
    total_users = db.query(User).count()
    total_articles = db.query(Article).count()
    
    # Publisher Breakdown
    from sqlalchemy import func
    sources = db.query(Article.source, func.count(Article.id)).group_by(Article.source).all()
    publisher_counts = {source or "TechNews": count for source, count in sources}
    
    return {
        "total_users": total_users,
        "total_articles": total_articles,
        "publisher_counts": publisher_counts,
        "scheduler_active": scheduler.running
    }

@app.post("/api/admin/trigger-scrape")
async def trigger_manual_scrape(admin: User = Depends(get_current_admin_user)):
    """Trigger manual multi-source RSS scraping and categorization"""
    try:
        from scrapers.techcrunch import fetch_and_save_all_sources
        fetch_and_save_all_sources()
        categorizer.sync_articles_from_files()
        categorizer.cleanup_old_articles(days=7)
        return {"status": "success", "message": "Multi-source scrape and categorization completed successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scrape execution failed: {str(e)}")

@app.delete("/api/admin/articles/{article_id}")
async def delete_article_admin(article_id: str, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    """Delete an article from database as admin"""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    db.query(ArticleCategory).filter(ArticleCategory.article_id == article_id).delete()
    db.delete(article)
    db.commit()
    return {"status": "success", "message": f"Article {article_id} deleted successfully."}