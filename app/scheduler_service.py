import os
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_scheduler():
    """Set up the scheduler for digest and notification tasks"""
    scheduler = BlockingScheduler()
    
    # Import here to avoid circular imports
    from services.digest_service import send_daily_digests, send_weekly_digests
    from services.categorization_service import sync_articles, cleanup_old_articles
    from scrapers.techcrunch import fetch_and_save_techcrunch_articles

    def scrape_and_sync():
        """Fetch fresh articles from TechCrunch, load new ones into the DB,
        and remove anything older than 7 days so the DB only ever holds a
        rolling week of news."""
        try:
            logger.info("Scraping latest TechCrunch articles...")
            fetch_and_save_techcrunch_articles()
        except Exception as e:
            logger.error(f"Scraping failed: {e}")

        try:
            logger.info("Syncing new articles into the database...")
            sync_articles()
        except Exception as e:
            logger.error(f"Sync failed: {e}")

        try:
            logger.info("Cleaning up articles older than 7 days...")
            cleanup_old_articles(days=7)
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
    
    # Schedule daily digest sending (9 AM every day)
    scheduler.add_job(
        func=send_daily_digests,
        trigger=CronTrigger(hour=9, minute=0),
        id='daily_digests',
        name='Send daily digests',
        replace_existing=True
    )
    
    # Schedule weekly digest sending (Monday 9 AM)
    scheduler.add_job(
        func=send_weekly_digests,
        trigger=CronTrigger(day_of_week='mon', hour=9, minute=0),
        id='weekly_digests',
        name='Send weekly digests',
        replace_existing=True
    )
    
    # Schedule article scraping + synchronization (every hour, at the top of the hour)
    scheduler.add_job(
        func=scrape_and_sync,
        trigger=CronTrigger(minute=0, second=0),
        id='scrape_and_sync_articles',
        name='Scrape TechCrunch and sync articles into DB',
        replace_existing=True
    )

    # Also run once immediately on startup, so you don't have to wait
    # up to an hour for the first refresh after (re)starting the scheduler
    scheduler.add_job(
        func=scrape_and_sync,
        id='scrape_and_sync_articles_startup',
        name='Initial scrape + sync on startup',
        replace_existing=True
    )
    
    # Log scheduled jobs
    logger.info("Scheduled jobs:")
    for job in scheduler.get_jobs():
        next_run = getattr(job, 'next_run_time', 'Pending scheduler startup')
        logger.info(f"  - {job.name} (ID: {job.id}) - Next run: {next_run}")
    
    return scheduler

def run_scheduler():
    """Run the scheduler"""
    logger.info("Starting digest scheduler...")
    
    # Initialize database first
    from app.database import init_database
    init_database()
    
    scheduler = setup_scheduler()
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        scheduler.shutdown()
    except Exception as e:
        logger.error(f"Scheduler error: {e}")
        scheduler.shutdown()

if __name__ == "__main__":
    run_scheduler()