from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

try:
    from backend.app.models import User, Article, Category, ArticleCategory, DigestLog, UserSubscription
    from backend.app.database import SessionLocal
except ImportError:
    from app.models import User, Article, Category, ArticleCategory, DigestLog, UserSubscription
    from app.database import SessionLocal

class DigestService:
    """Service for retrieving personalized articles for users"""
    
    def __init__(self):
        pass
    
    def get_user_interests(self, db: Session, user: User) -> List[Category]:
        """Get categories that the user is interested in"""
        return user.interests
    
    def get_articles_for_user(self, db: Session, user: User, days_back: int = 7, 
                            max_articles_per_category: int = 5) -> Dict[str, List[Article]]:
        """Get personalized articles for a user based on their selected topics"""
        user_categories = self.get_user_interests(db, user)
        
        if not user_categories:
            user_categories = db.query(Category).all()
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        articles_by_category = {}
        
        for category in user_categories:
            articles = (db.query(Article)
                       .join(ArticleCategory)
                       .filter(
                           and_(
                               ArticleCategory.category_id == category.id,
                               Article.created_at >= cutoff_date
                           )
                       )
                       .order_by(
                           desc(ArticleCategory.relevance_score),
                           desc(Article.created_at)
                       )
                       .limit(max_articles_per_category)
                       .all())
            
            if articles:
                articles_by_category[category.name] = articles
        
        return articles_by_category

# Global instance
digest_service = DigestService()