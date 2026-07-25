import os
from dotenv import load_dotenv
load_dotenv()

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Dict
from jinja2 import Template
from app.models import User, Article, Category
import asyncio
import aiosmtplib

class EmailService:
    """Service for sending personalized email digests and notifications"""
    
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("FROM_EMAIL", self.smtp_username)
        self.from_name = os.getenv("FROM_NAME", "Tech News Digest")
    
    def get_daily_digest_template(self) -> str:
        """HTML template for daily digest emails"""
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your Daily Tech Digest</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f4f4f4; }
        .container { max-width: 600px; margin: 0 auto; background-color: #ffffff; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px 20px; text-align: center; }
        .header h1 { margin: 0; font-size: 28px; font-weight: 300; }
        .header p { margin: 10px 0 0 0; opacity: 0.9; }
        .content { padding: 20px; }
        .greeting { font-size: 18px; margin-bottom: 25px; color: #444; }
        .category { margin-bottom: 35px; }
        .category-title { color: #667eea; font-size: 20px; font-weight: 600; margin-bottom: 15px; border-bottom: 2px solid #667eea; padding-bottom: 5px; }
        .article { background: #f8f9fa; border-radius: 8px; padding: 20px; margin-bottom: 15px; border-left: 4px solid #667eea; }
        .article-title { color: #2d3748; font-size: 16px; font-weight: 600; margin-bottom: 8px; }
        .article-title a { color: #2d3748; text-decoration: none; }
        .article-title a:hover { color: #667eea; }
        .article-summary { color: #666; font-size: 14px; line-height: 1.5; margin-bottom: 10px; }
        .article-meta { font-size: 12px; color: #999; }
        .footer { background-color: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #eee; }
        .footer p { margin: 5px 0; color: #666; font-size: 14px; }
        .unsubscribe { color: #999; font-size: 12px; }
        .unsubscribe a { color: #667eea; text-decoration: none; }
        .stats { background: #e6f4ea; border-radius: 6px; padding: 15px; margin: 20px 0; text-align: center; }
        .stats-number { font-size: 24px; font-weight: bold; color: #176148; }
        .stats-label { color: #176148; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Your Daily Tech Digest</h1>
            <p>{{ date.strftime('%A, %B %d, %Y') }}</p>
        </div>
        
        <div class="content">
            <div class="greeting">
                Hi {{ user.full_name or 'there' }}! 👋
            </div>
            
            <div class="stats">
                <div class="stats-number">{{ total_articles }}</div>
                <div class="stats-label">personalized articles for you today</div>
            </div>
            
            {% for category_name, articles in categories.items() %}
            <div class="category">
                <div class="category-title">{{ category_name }}</div>
                
                {% for article in articles %}
                <div class="article">
                    <div class="article-title">
                        <a href="{{ article.link }}" target="_blank">{{ article.title }}</a>
                    </div>
                    <div class="article-summary">
                        {{ article.llm_summary or article.summary[:200] + '...' if article.summary|length > 200 else article.summary }}
                    </div>
                    <div class="article-meta">
                        Published: {{ article.published or 'Recently' }}
                    </div>
                </div>
                {% endfor %}
            </div>
            {% endfor %}
            
            {% if not categories %}
            <div style="text-align: center; color: #666; padding: 40px 20px;">
                <h3>No new articles today</h3>
                <p>Check back tomorrow for fresh tech news tailored to your interests!</p>
            </div>
            {% endif %}
        </div>
        
        <div class="footer">
            <p><strong>Tech News Digest</strong></p>
            <p>Stay ahead of the curve with personalized tech news.</p>
            <p class="unsubscribe">
                <a href="{{ unsubscribe_url }}">Manage preferences</a> | 
                <a href="{{ unsubscribe_url }}">Unsubscribe</a>
            </p>
        </div>
    </div>
</body>
</html>
        """
    
    def get_weekly_digest_template(self) -> str:
        """HTML template for weekly digest emails"""
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your Weekly Tech Roundup</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f4f4f4; }
        .container { max-width: 600px; margin: 0 auto; background-color: #ffffff; }
        .header { background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); color: #8b4513; padding: 30px 20px; text-align: center; }
        .header h1 { margin: 0; font-size: 28px; font-weight: 300; }
        .header p { margin: 10px 0 0 0; opacity: 0.8; }
        .content { padding: 20px; }
        .greeting { font-size: 18px; margin-bottom: 25px; color: #444; }
        .summary-box { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 25px; text-align: center; }
        .summary-number { font-size: 32px; font-weight: bold; margin-bottom: 5px; }
        .summary-text { font-size: 16px; opacity: 0.9; }
        .category { margin-bottom: 35px; }
        .category-title { color: #8b4513; font-size: 20px; font-weight: 600; margin-bottom: 15px; border-bottom: 2px solid #fcb69f; padding-bottom: 5px; }
        .article { background: #f8f9fa; border-radius: 8px; padding: 20px; margin-bottom: 15px; border-left: 4px solid #fcb69f; }
        .article-title { color: #2d3748; font-size: 16px; font-weight: 600; margin-bottom: 8px; }
        .article-title a { color: #2d3748; text-decoration: none; }
        .article-title a:hover { color: #8b4513; }
        .article-summary { color: #666; font-size: 14px; line-height: 1.5; margin-bottom: 10px; }
        .article-meta { font-size: 12px; color: #999; }
        .footer { background-color: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #eee; }
        .footer p { margin: 5px 0; color: #666; font-size: 14px; }
        .unsubscribe { color: #999; font-size: 12px; }
        .unsubscribe a { color: #8b4513; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Your Weekly Tech Roundup</h1>
            <p>{{ start_date.strftime('%B %d') }} - {{ end_date.strftime('%B %d, %Y') }}</p>
        </div>
        
        <div class="content">
            <div class="greeting">
                Hi {{ user.full_name or 'there' }}! 📈
            </div>
            
            <div class="summary-box">
                <div class="summary-number">{{ total_articles }}</div>
                <div class="summary-text">articles this week across {{ category_count }} categories</div>
            </div>
            
            {% for category_name, articles in categories.items() %}
            <div class="category">
                <div class="category-title">{{ category_name }} ({{ articles|length }} articles)</div>
                
                {% for article in articles %}
                <div class="article">
                    <div class="article-title">
                        <a href="{{ article.link }}" target="_blank">{{ article.title }}</a>
                    </div>
                    <div class="article-summary">
                        {{ article.llm_summary or article.summary[:200] + '...' if article.summary|length > 200 else article.summary }}
                    </div>
                    <div class="article-meta">
                        Published: {{ article.published or 'This week' }}
                    </div>
                </div>
                {% endfor %}
            </div>
            {% endfor %}
        </div>
        
        <div class="footer">
            <p><strong>Tech News Digest</strong></p>
            <p>Your weekly dose of curated tech news.</p>
            <p class="unsubscribe">
                <a href="{{ unsubscribe_url }}">Manage preferences</a> | 
                <a href="{{ unsubscribe_url }}">Unsubscribe</a>
            </p>
        </div>
    </div>
</body>
</html>
        """
    
    def generate_digest_email(self, user: User, articles_by_category: Dict[str, List[Article]], 
                            digest_type: str = "daily") -> tuple[str, str]:
        """Generate email subject and HTML content for digest"""
        
        total_articles = sum(len(articles) for articles in articles_by_category.values())
        
        if digest_type == "daily":
            template = Template(self.get_daily_digest_template())
            subject = f"🚀 Your Daily Tech Digest - {total_articles} articles"
            
            html_content = template.render(
                user=user,
                categories=articles_by_category,
                total_articles=total_articles,
                date=datetime.now(),
                unsubscribe_url=f"https://your-domain.com/unsubscribe/{user.id}"
            )
        else:  # weekly
            template = Template(self.get_weekly_digest_template())
            subject = f"📊 Your Weekly Tech Roundup - {total_articles} articles"
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            html_content = template.render(
                user=user,
                categories=articles_by_category,
                total_articles=total_articles,
                category_count=len(articles_by_category),
                start_date=start_date,
                end_date=end_date,
                unsubscribe_url=f"https://your-domain.com/unsubscribe/{user.id}"
            )
        
        return subject, html_content
    
    async def send_email_async(self, to_email: str, subject: str, html_content: str) -> bool:
        """Send email asynchronously using aiosmtplib"""
        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            
            # Create HTML part
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email
            await aiosmtplib.send(
                message,
                hostname=self.smtp_server,
                port=self.smtp_port,
                start_tls=True,
                username=self.smtp_username,
                password=self.smtp_password,
            )
            
            return True
            
        except Exception as e:
            print(f"Error sending email to {to_email}: {e}")
            return False
    
    def send_email_sync(self, to_email: str, subject: str, html_content: str) -> bool:
        """Send email synchronously using smtplib"""
        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            
            # Create HTML part
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)
            
            return True
            
        except Exception as e:
            print(f"Error sending email to {to_email}: {e}")
            return False
    
    def send_instant_notification(self, user: User, article: Article) -> bool:
        """Send instant notification for breaking news"""
        subject = f"🔥 Breaking: {article.title}"
        
        template = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 500px; margin: 0 auto; padding: 20px; }
                .header { background: #ff6b6b; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }
                .content { background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }
                .article-title { font-size: 18px; font-weight: bold; margin-bottom: 10px; }
                .article-summary { margin-bottom: 15px; }
                .read-more { background: #ff6b6b; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>🔥 Breaking Tech News</h2>
                </div>
                <div class="content">
                    <div class="article-title">{{ article.title }}</div>
                    <div class="article-summary">{{ article.llm_summary or article.summary[:300] }}</div>
                    <a href="{{ article.link }}" class="read-more" target="_blank">Read Full Article</a>
                </div>
            </div>
        </body>
        </html>
        """)
        
        html_content = template.render(article=article)
        return self.send_email_sync(user.email, subject, html_content)

# Global instance
email_service = EmailService()