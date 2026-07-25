from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from collections import defaultdict

from app.models import User, Article, Category, ArticleCategory, DigestLog, UserSubscription
from services.email_service import email_service
from services.categorization_service import categorizer
from app.database import SessionLocal

class DigestService:
    """Service for generating and sending personalized digests"""
    
    def __init__(self):
        pass
    
    def get_user_interests(self, db: Session, user: User) -> List[Category]:
        """Get categories that the user is interested in"""
        return user.interests
    
    def get_articles_for_user(self, db: Session, user: User, days_back: int = 1, 
                            max_articles_per_category: int = 5) -> Dict[str, List[Article]]:
        """Get personalized articles for a user based on their interests"""
        
        # Get user's interested categories
        user_categories = self.get_user_interests(db, user)
        
        if not user_categories:
            # If user has no specific interests, get from all categories
            user_categories = db.query(Category).all()
        
        # Calculate date threshold
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        articles_by_category = {}
        
        for category in user_categories:
            # Get articles for this category from the last N days
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
        
        # Also check for custom keyword subscriptions
        custom_subscriptions = (db.query(UserSubscription)
                              .filter(
                                  and_(
                                      UserSubscription.user_id == user.id,
                                      UserSubscription.is_active == True,
                                      UserSubscription.keywords.isnot(None)
                                  )
                              )
                              .all())
        
        for subscription in custom_subscriptions:
            if subscription.keywords:
                custom_articles = categorizer.get_articles_by_keywords(
                    db, subscription.keywords, limit=max_articles_per_category
                )
                
                # Filter by date
                recent_articles = [
                    article for article in custom_articles 
                    if article.created_at >= cutoff_date
                ]
                
                if recent_articles:
                    key = f"Custom: {', '.join(subscription.keywords[:3])}"
                    articles_by_category[key] = recent_articles
        
        return articles_by_category
    
    def should_send_digest(self, db: Session, user: User, digest_type: str) -> bool:
        """Check if we should send a digest to this user"""
        
        # Check user preferences
        if digest_type == "daily" and not user.daily_digest_enabled:
            return False
        if digest_type == "weekly" and not user.weekly_digest_enabled:
            return False
        
        # Check if we already sent a digest today/this week
        if digest_type == "daily":
            cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        else:  # weekly
            # Check if we sent in the last 7 days
            cutoff = datetime.now() - timedelta(days=7)
        
        recent_digest = (db.query(DigestLog)
                        .filter(
                            and_(
                                DigestLog.user_id == user.id,
                                DigestLog.digest_type == digest_type,
                                DigestLog.sent_at >= cutoff,
                                DigestLog.email_status == "sent"
                            )
                        )
                        .first())
        
        return recent_digest is None
    
    def generate_daily_digest(self, db: Session, user: User) -> bool:
        """Generate and send daily digest for a user"""
        
        if not self.should_send_digest(db, user, "daily"):
            return False
        
        # Get articles from the last 24 hours
        articles_by_category = self.get_articles_for_user(db, user, days_back=1)
        
        if not articles_by_category:
            print(f"No articles found for user {user.email}, skipping daily digest")
            return False
        
        # Generate email content
        subject, html_content = email_service.generate_digest_email(
            user, articles_by_category, "daily"
        )
        
        # Send email
        success = email_service.send_email_sync(user.email, subject, html_content)
        
        # Log the digest attempt
        total_articles = sum(len(articles) for articles in articles_by_category.values())
        digest_log = DigestLog(
            user_id=user.id,
            digest_type="daily",
            article_count=total_articles,
            email_status="sent" if success else "failed"
        )
        db.add(digest_log)
        db.commit()
        
        if success:
            print(f"Sent daily digest to {user.email} with {total_articles} articles")
        else:
            print(f"Failed to send daily digest to {user.email}")
        
        return success
    
    def generate_weekly_digest(self, db: Session, user: User) -> bool:
        """Generate and send weekly digest for a user"""
        
        if not self.should_send_digest(db, user, "weekly"):
            return False
        
        # Get articles from the last 7 days
        articles_by_category = self.get_articles_for_user(db, user, days_back=7, max_articles_per_category=10)
        
        if not articles_by_category:
            print(f"No articles found for user {user.email}, skipping weekly digest")
            return False
        
        # Generate email content
        subject, html_content = email_service.generate_digest_email(
            user, articles_by_category, "weekly"
        )
        
        # Send email
        success = email_service.send_email_sync(user.email, subject, html_content)
        
        # Log the digest attempt
        total_articles = sum(len(articles) for articles in articles_by_category.values())
        digest_log = DigestLog(
            user_id=user.id,
            digest_type="weekly",
            article_count=total_articles,
            email_status="sent" if success else "failed"
        )
        db.add(digest_log)
        db.commit()
        
        if success:
            print(f"Sent weekly digest to {user.email} with {total_articles} articles")
        else:
            print(f"Failed to send weekly digest to {user.email}")
        
        return success
    
    def send_daily_digests(self):
        """Send daily digests to all eligible users"""
        db = SessionLocal()
        try:
            # Get all active users who have daily digest enabled
            users = (db.query(User)
                    .filter(
                        and_(
                            User.is_active == True,
                            User.daily_digest_enabled == True
                        )
                    )
                    .all())
            
            print(f"Processing daily digests for {len(users)} users")
            
            sent_count = 0
            for user in users:
                try:
                    if self.generate_daily_digest(db, user):
                        sent_count += 1
                except Exception as e:
                    print(f"Error sending daily digest to {user.email}: {e}")
            
            print(f"Successfully sent {sent_count} daily digests")
            
        except Exception as e:
            print(f"Error processing daily digests: {e}")
        finally:
            db.close()
    
    def send_weekly_digests(self):
        """Send weekly digests to all eligible users"""
        db = SessionLocal()
        try:
            # Get all active users who have weekly digest enabled
            users = (db.query(User)
                    .filter(
                        and_(
                            User.is_active == True,
                            User.weekly_digest_enabled == True
                        )
                    )
                    .all())
            
            print(f"Processing weekly digests for {len(users)} users")
            
            sent_count = 0
            for user in users:
                try:
                    if self.generate_weekly_digest(db, user):
                        sent_count += 1
                except Exception as e:
                    print(f"Error sending weekly digest to {user.email}: {e}")
            
            print(f"Successfully sent {sent_count} weekly digests")
            
        except Exception as e:
            print(f"Error processing weekly digests: {e}")
        finally:
            db.close()
    
    def send_instant_notifications(self, article_data: Dict):
        """Send instant notifications for breaking news to subscribed users"""
        db = SessionLocal()
        try:
            # Get users who have instant notifications enabled
            users = (db.query(User)
                    .filter(
                        and_(
                            User.is_active == True,
                            User.instant_notifications == True
                        )
                    )
                    .all())
            
            if not users:
                return
            
            # Create article object for email template
            article = Article(
                title=article_data.get('title', ''),
                link=article_data.get('link', ''),
                summary=article_data.get('summary', ''),
                llm_summary=article_data.get('llm_summary', '')
            )
            
            # Categorize the article to determine relevance
            categorizations = categorizer.categorize_article(article_data, db)
            
            if not categorizations:
                return  # Article doesn't match any categories
            
            relevant_category_ids = [cat_id for cat_id, score in categorizations if score >= 7]  # Only high-relevance articles
            
            if not relevant_category_ids:
                return
            
            # Find users interested in these categories
            interested_users = []
            for user in users:
                user_category_ids = [cat.id for cat in user.interests]
                if any(cat_id in user_category_ids for cat_id in relevant_category_ids):
                    interested_users.append(user)
            
            # Send notifications
            sent_count = 0
            for user in interested_users:
                try:
                    if email_service.send_instant_notification(user, article):
                        sent_count += 1
                except Exception as e:
                    print(f"Error sending instant notification to {user.email}: {e}")
            
            print(f"Sent {sent_count} instant notifications for: {article.title}")
            
        except Exception as e:
            print(f"Error processing instant notifications: {e}")
        finally:
            db.close()

# Global instance
digest_service = DigestService()

def send_daily_digests():
    """Function to be called by scheduler"""
    digest_service.send_daily_digests()

def send_weekly_digests():
    """Function to be called by scheduler"""
    digest_service.send_weekly_digests()

if __name__ == "__main__":
    # Test daily digest generation
    send_daily_digests()