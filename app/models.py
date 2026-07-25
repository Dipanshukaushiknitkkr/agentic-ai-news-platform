from sqlalchemy import Boolean, Column, Integer, String, DateTime, Text, ForeignKey, Table, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid

Base = declarative_base()

# Association table for user interests (many-to-many relationship)
user_interests = Table(
    'user_interests',
    Base.metadata,
    Column('user_id', String, ForeignKey('users.id')),
    Column('category_id', Integer, ForeignKey('categories.id'))
)

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Digest preferences
    daily_digest_enabled = Column(Boolean, default=True)
    weekly_digest_enabled = Column(Boolean, default=True)
    instant_notifications = Column(Boolean, default=False)
    digest_time = Column(String, default="09:00")  # HH:MM format
    time_zone = Column(String, default="UTC")
    
    # Relationships
    interests = relationship("Category", secondary=user_interests, back_populates="users")
    subscriptions = relationship("UserSubscription", back_populates="user")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)
    keywords = Column(JSON)  # List of keywords for automatic categorization
    
    # Relationships
    users = relationship("User", secondary=user_interests, back_populates="interests")
    articles = relationship("ArticleCategory", back_populates="category")

class Article(Base):
    __tablename__ = "articles"
    
    id = Column(String, primary_key=True)  # Will use filename as ID
    title = Column(String, nullable=False)
    link = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    llm_summary = Column(Text, nullable=True)
    published = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    categories = relationship("ArticleCategory", back_populates="article")

class ArticleCategory(Base):
    __tablename__ = "article_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(String, ForeignKey("articles.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    relevance_score = Column(Integer, default=1)  # 1-10 scale
    
    # Relationships
    article = relationship("Article", back_populates="categories")
    category = relationship("Category", back_populates="articles")

class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"))
    subscription_type = Column(String)  # "daily", "weekly", "instant"
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    keywords = Column(JSON, nullable=True)  # Custom keywords for this subscription
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")

class DigestLog(Base):
    __tablename__ = "digest_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"))
    digest_type = Column(String)  # "daily", "weekly"
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    article_count = Column(Integer, default=0)
    email_status = Column(String, default="pending")  # "pending", "sent", "failed"
    
class NotificationLog(Base):
    __tablename__ = "notification_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"))
    article_id = Column(String, ForeignKey("articles.id"))
    notification_type = Column(String)  # "instant", "digest"
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, default="pending")  # "pending", "sent", "failed"