from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict
from datetime import datetime

# Authentication schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    is_active: bool
    daily_digest_enabled: bool
    weekly_digest_enabled: bool
    instant_notifications: bool
    digest_time: str
    time_zone: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# Category schemas
class CategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    keywords: List[str]
    
    class Config:
        from_attributes = True

# Article schemas
class ArticleResponse(BaseModel):
    id: str
    title: str
    link: str
    summary: Optional[str]
    llm_summary: Optional[str]
    published: Optional[str]
    image_url: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class ArticleWithCategories(ArticleResponse):
    categories: List[CategoryResponse]

# Subscription schemas
class SubscriptionCreate(BaseModel):
    subscription_type: str  # "daily", "weekly", "instant"
    category_id: Optional[int] = None
    keywords: Optional[List[str]] = None

class SubscriptionResponse(BaseModel):
    id: int
    subscription_type: str
    category_id: Optional[int]
    keywords: Optional[List[str]]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# User preferences schemas
class DigestPreferences(BaseModel):
    daily_digest_enabled: bool
    weekly_digest_enabled: bool
    instant_notifications: bool
    digest_time: str
    time_zone: str
    interested_categories: List[int]

class PreferencesUpdate(BaseModel):
    daily_digest_enabled: Optional[bool] = None
    weekly_digest_enabled: Optional[bool] = None
    instant_notifications: Optional[bool] = None
    digest_time: Optional[str] = None
    time_zone: Optional[str] = None
    interested_categories: Optional[List[int]] = None

# Digest schemas
class DigestPreview(BaseModel):
    total_articles: int
    categories: Dict[str, List[ArticleResponse]]
    digest_type: str

class DigestLogResponse(BaseModel):
    id: int
    digest_type: str
    sent_at: datetime
    article_count: int
    email_status: str
    
    class Config:
        from_attributes = True

# Dashboard schemas
class UserStats(BaseModel):
    total_articles_read: int
    digest_count: int
    favorite_categories: List[str]
    last_digest_sent: Optional[datetime]

class SystemStats(BaseModel):
    total_users: int
    active_subscribers: int
    articles_processed_today: int
    digests_sent_today: int