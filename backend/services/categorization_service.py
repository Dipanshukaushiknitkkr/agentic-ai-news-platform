import os
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.app.models import Article, Category, ArticleCategory
    from backend.app.database import get_db, SessionLocal
except ImportError:
    from app.models import Article, Category, ArticleCategory
    from app.database import get_db, SessionLocal

class ContentCategorizer:
    """Service for automatically categorizing articles based on content"""
    
    def __init__(self):
        self.categories_cache = None
        self.stopwords = set(['the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'for', 'to', 'of', 'in', 'with', 'by', 'as', 'from', 'that', 'this', 'it', 'are', 'be', 'was', 'were', 'has', 'had', 'have', 'but', 'not', 'if', 'then', 'so', 'do', 'does', 'did', 'can', 'will', 'just', 'about', 'into', 'over', 'after', 'before', 'more', 'less', 'than', 'up', 'out', 'off', 'no', 'yes', 'you', 'i', 'we', 'they', 'he', 'she', 'his', 'her', 'their', 'our', 'my', 'your'])
    
    def get_categories(self, db: Session) -> List[Category]:
        """Get all categories with their keywords"""
        if self.categories_cache is None:
            self.categories_cache = db.query(Category).all()
        return self.categories_cache
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        # Convert to lowercase and extract words
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        # Remove stopwords
        keywords = [word for word in words if word not in self.stopwords]
        return keywords
    
    def calculate_relevance_score(self, title: str, content: str, category_keywords: List[str]) -> int:
        """Calculate relevance score (1-10) for an article to a category with title boosting"""
        title_lower = title.lower()
        content_lower = content.lower()
        
        matches = 0
        title_bonus = 0
        
        for keyword in category_keywords:
            keyword_lower = keyword.lower()
            pattern = r'\b' + re.escape(keyword_lower) + r'\b'
            
            # Check title match (2x weight)
            if re.search(pattern, title_lower):
                title_bonus += 2
                matches += 1
            # Check content/summary match
            elif re.search(pattern, content_lower):
                matches += 1
        
        if matches == 0 and title_bonus == 0:
            return 0
        
        score = min(10, (matches * 2) + title_bonus + 1)
        return score
    
    def categorize_article(self, article_data: Dict, db: Session) -> List[Tuple[int, int]]:
        """Categorize a single article and return list of (category_id, relevance_score) tuples"""
        categories = self.get_categories(db)
        title = article_data.get('title', '')
        content = f"{article_data.get('summary', '')} {article_data.get('llm_summary', '')}"
        
        categorizations = []
        for category in categories:
            if not category.keywords:
                continue
                
            relevance_score = self.calculate_relevance_score(title, content, category.keywords)
            if relevance_score >= 2:
                categorizations.append((category.id, relevance_score))
        
        categorizations.sort(key=lambda x: x[1], reverse=True)
        return categorizations[:4]

    def recategorize_all_existing_articles(self, db: Session = None) -> int:
        """Re-scan all database articles and tag them with updated taxonomy keywords"""
        owns_session = False
        if db is None:
            db = SessionLocal()
            owns_session = True
            
        try:
            self.categories_cache = None  # Reset cache
            articles = db.query(Article).all()
            re_tagged = 0
            
            for article in articles:
                # Clear existing category tags
                db.query(ArticleCategory).filter(ArticleCategory.article_id == article.id).delete()
                
                article_data = {
                    'title': article.title,
                    'summary': article.summary or '',
                    'llm_summary': article.llm_summary or ''
                }
                categorizations = self.categorize_article(article_data, db)
                
                for category_id, relevance_score in categorizations:
                    db.add(ArticleCategory(
                        article_id=article.id,
                        category_id=category_id,
                        relevance_score=relevance_score
                    ))
                if categorizations:
                    re_tagged += 1
                    
            db.commit()
            print(f"Re-categorization complete: Successfully tagged {re_tagged} of {len(articles)} articles.")
            return re_tagged
        except Exception as e:
            print(f"Error in recategorize_all_existing_articles: {e}")
            db.rollback()
            return 0
        finally:
            if owns_session:
                db.close()
    
    def cleanup_old_articles(self, db: Session = None, days: int = 7):
        """Delete articles (and their category links) older than `days` days.
        Uses Article.created_at, since `published` is a raw RSS string and not
        reliably parseable/sortable across feeds. Also deletes the matching
        .md/.json files in data/summaries/ so they aren't re-synced back in
        on the next sync pass.
        """
        owns_session = db is None
        if owns_session:
            db = SessionLocal()
        try:
            total_articles = db.query(Article).count()
            if total_articles <= 15:
                print("Cleanup skipped: preserving minimum 15 articles.")
                return 0

            cutoff = datetime.utcnow() - timedelta(days=days)
            old_articles = db.query(Article).filter(Article.created_at < cutoff).all()
            
            # Keep at least 15 most recent articles
            if total_articles - len(old_articles) < 15:
                # Sort old articles descending by date and keep enough to maintain 15
                old_articles.sort(key=lambda a: a.created_at, reverse=True)
                allowed_to_delete = total_articles - 15
                old_articles = old_articles[allowed_to_delete:]

            deleted_count = len(old_articles)
            for article in old_articles:
                db.query(ArticleCategory).filter(ArticleCategory.article_id == article.id).delete()
                db.delete(article)
            db.commit()
            print(f"Cleanup: removed {deleted_count} old articles.")
            return deleted_count
        except Exception as e:
            print(f"Error cleaning up old articles: {e}")
            db.rollback()
            return 0
        finally:
            if owns_session:
                db.close()

    def is_duplicate_title(self, new_title: str, existing_titles: List[str], jaccard_thresh=0.48, seq_thresh=0.62) -> bool:
        """Check if new_title is a duplicate of any existing headline"""
        from difflib import SequenceMatcher
        stopwords = set(['the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'for', 'to', 'of', 'in', 'with', 'by', 'as', 'from', 'that', 'this', 'it', 'are', 'be', 'was', 'were', 'has', 'had', 'have', 'but', 'not', 'if', 'then', 'so', 'do', 'does', 'did', 'can', 'will', 'just', 'about', 'into', 'over', 'after', 'before', 'more', 'less', 'than', 'up', 'out', 'off', 'no', 'yes', 'you', 'new', 'says', 'how', 'why', 'what', 'announced', 'announces', 'launches', 'unveils'])
        
        def get_clean_tokens(t):
            words = re.findall(r'\b[a-zA-Z0-9]{3,}\b', t.lower())
            return set(w for w in words if w not in stopwords)
            
        new_tokens = get_clean_tokens(new_title)
        if not new_tokens:
            return False
            
        for existing in existing_titles:
            ext_tokens = get_clean_tokens(existing)
            if not ext_tokens:
                continue
            intersection = len(new_tokens & ext_tokens)
            union = len(new_tokens | ext_tokens)
            jaccard = intersection / union if union > 0 else 0
            seq_ratio = SequenceMatcher(None, new_title.lower(), existing.lower()).ratio()
            
            if (jaccard >= jaccard_thresh and intersection >= 3) or seq_ratio >= seq_thresh:
                return True
        return False

    def sync_articles_from_files(self, summaries_dir: str = 'data/summaries/'):
        """Sync articles from JSON files to database with cross-publisher deduplication"""
        db = SessionLocal()
        try:
            if not os.path.exists(summaries_dir):
                print(f"Summaries directory not found: {summaries_dir}")
                return
            
            # Fetch recent titles from database for deduplication
            cutoff_48h = datetime.utcnow() - timedelta(hours=48)
            existing_articles = db.query(Article.id, Article.title).filter(Article.created_at >= cutoff_48h).all()
            existing_ids = set(a.id for a in existing_articles)
            existing_titles = [a.title for a in existing_articles]
            
            processed_count = 0
            categorized_count = 0
            duplicates_skipped = 0
            
            for filename in sorted(os.listdir(summaries_dir), reverse=True):
                if not filename.endswith('.json'):
                    continue
                
                filepath = os.path.join(summaries_dir, filename)
                article_id = filename.replace('.json', '')
                
                # Check exact ID match
                if article_id in existing_ids:
                    continue
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        article_data = json.load(f)
                    
                    title = article_data.get('title', '')
                    if not title:
                        continue
                        
                    # Check cross-publisher duplicate headline
                    if self.is_duplicate_title(title, existing_titles):
                        duplicates_skipped += 1
                        continue
                    
                    # Parse publication date or filename date prefix
                    pub_str = article_data.get('published', '')
                    created_at_dt = datetime.now()
                    if pub_str:
                        try:
                            from email.utils import parsedate_to_datetime
                            created_at_dt = parsedate_to_datetime(pub_str).replace(tzinfo=None)
                        except Exception:
                            pass
                    if created_at_dt.date() == datetime.now().date():
                        try:
                            parts = filename.split('-')[:3]
                            created_at_dt = datetime.strptime('-'.join(parts), '%Y-%m-%d')
                        except Exception:
                            pass

                    # Create article record
                    article = Article(
                        id=article_id,
                        title=title,
                        link=article_data.get('link', ''),
                        summary=article_data.get('summary', ''),
                        llm_summary=article_data.get('llm_summary', ''),
                        published=article_data.get('published', ''),
                        image_url=article_data.get('image_url', ''),
                        source=article_data.get('source', 'TechNews'),
                        created_at=created_at_dt
                    )
                    db.add(article)
                    db.flush()
                    
                    # Categorize the article
                    categorizations = self.categorize_article(article_data, db)
                    
                    for category_id, relevance_score in categorizations:
                        article_category = ArticleCategory(
                            article_id=article_id,
                            category_id=category_id,
                            relevance_score=relevance_score
                        )
                        db.add(article_category)
                    
                    existing_titles.append(title)
                    existing_ids.add(article_id)
                    processed_count += 1
                    if categorizations:
                        categorized_count += 1
                    
                except Exception as e:
                    print(f"Error processing {filename}: {e}")
                    continue
            
            db.commit()
            print(f"Sync complete: Added {processed_count} unique articles (Skipped {duplicates_skipped} duplicate stories).")
            
        except Exception as e:
            print(f"Error syncing articles: {e}")
            db.rollback()
        finally:
            db.close()

    def deduplicate_existing_database(self, db: Session = None) -> int:
        """Scan and purge duplicate articles currently in the database"""
        owns_session = False
        if db is None:
            db = SessionLocal()
            owns_session = True
            
        try:
            articles = db.query(Article).order_by(Article.created_at.desc()).all()
            unique_titles = []
            duplicates_to_delete = []
            
            for art in articles:
                if self.is_duplicate_title(art.title, unique_titles):
                    duplicates_to_delete.append(art)
                else:
                    unique_titles.append(art.title)
                    
            deleted_count = len(duplicates_to_delete)
            for dup in duplicates_to_delete:
                db.query(ArticleCategory).filter(ArticleCategory.article_id == dup.id).delete()
                db.delete(dup)
                
            db.commit()
            print(f"Database deduplication cleanup: Purged {deleted_count} duplicate stories.")
            return deleted_count
        except Exception as e:
            print(f"Error in database deduplication: {e}")
            db.rollback()
            return 0
        finally:
            if owns_session:
                db.close()
    
    def get_articles_by_category(self, db: Session, category_id: int, limit: int = 10) -> List[Article]:
        """Get articles for a specific category"""
        return (db.query(Article)
                .join(ArticleCategory)
                .filter(ArticleCategory.category_id == category_id)
                .order_by(ArticleCategory.relevance_score.desc(), Article.created_at.desc())
                .limit(limit)
                .all())
    
    def get_articles_by_keywords(self, db: Session, keywords: List[str], limit: int = 10) -> List[Article]:
        """Get articles that match specific keywords"""
        if not keywords:
            return []
        
        # Create a search pattern
        search_terms = [f"%{keyword.lower()}%" for keyword in keywords]
        
        articles = []
        for term in search_terms:
            matching_articles = (db.query(Article)
                               .filter(
                                   (Article.title.ilike(term)) |
                                   (Article.summary.ilike(term)) |
                                   (Article.llm_summary.ilike(term))
                               )
                               .order_by(Article.created_at.desc())
                               .limit(limit)
                               .all())
            articles.extend(matching_articles)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_articles = []
        for article in articles:
            if article.id not in seen:
                seen.add(article.id)
                unique_articles.append(article)
        
        return unique_articles[:limit]

# Global instance
categorizer = ContentCategorizer()

def categorize_new_article(article_data: Dict) -> List[Tuple[int, int]]:
    """Categorize a newly scraped article"""
    db = SessionLocal()
    try:
        return categorizer.categorize_article(article_data, db)
    finally:
        db.close()

def sync_articles():
    """Sync articles from files to database"""
    categorizer.sync_articles_from_files()

def cleanup_old_articles(days: int = 7):
    """Remove articles older than `days` days from the database"""
    categorizer.cleanup_old_articles(days=days)

if __name__ == "__main__":
    sync_articles()