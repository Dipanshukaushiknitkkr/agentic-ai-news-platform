import schedule
import time
import subprocess

def run_scraper():
    print("Running scraper...")
    subprocess.run(["python", "scrapers/techcrunch.py"])
    print("Scraper run complete.")

# Schedule: every day at 8:00 AM
schedule.every().day.at("08:00").do(run_scraper)

print("Scheduler started. Waiting for next run...")
while True:
    schedule.run_pending()
    time.sleep(60) 