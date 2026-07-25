# run_all.py
import subprocess
import sys
import os
import time

def run():
    # Detect the correct virtual environment executables
    python_exe = os.path.join(".venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable  # Fallback to current python interpreter

    uvicorn_exe = os.path.join(".venv", "Scripts", "uvicorn.exe")
    if not os.path.exists(uvicorn_exe):
        uvicorn_cmd = [python_exe, "-m", "uvicorn", "app.webapp:app", "--reload"]
    else:
        uvicorn_cmd = [uvicorn_exe, "app.webapp:app", "--reload"]

    scheduler_cmd = [python_exe, "-m", "app.scheduler_service"]

    print("[INFO] Starting Tech News Digest Services...")
    
    # 1. Start Scraper and DB Sync as a single background process
    # This prevents blocking the web server startup and runs news updates asynchronously.
    # NOTE: no artificial timeout here anymore -- scraping + LLM summarization of a full
    # RSS feed routinely takes well over a minute, and an 8s timeout was killing this
    # step almost every time before it could write anything, which is why articles
    # were never actually refreshing. The recurring hourly refresh is handled by
    # scheduler_service.py; this is just a one-time "catch up now" run on startup.
    update_script = (
        "import sys; "
        "print('[INFO] Background: Fetching latest articles...'); "
        "try:\n"
        "    from scrapers.techcrunch import fetch_and_save_techcrunch_articles\n"
        "    fetch_and_save_techcrunch_articles()\n"
        "    print('[SUCCESS] Background: Scraper finished.')\n"
        "except Exception as e:\n"
        "    print(f'[WARNING] Background: Scraper failed: {e}')\n"
        "print('[INFO] Background: Syncing articles to database...'); "
        "try:\n"
        "    from services.categorization_service import categorizer\n"
        "    categorizer.sync_articles_from_files()\n"
        "    print('[SUCCESS] Background: Database sync finished.')\n"
        "except Exception as e:\n"
        "    print(f'[WARNING] Background: Database sync failed: {e}')\n"
    )

    update_process = subprocess.Popen([python_exe, "-c", update_script])

    # Launch uvicorn web server
    web_process = subprocess.Popen(uvicorn_cmd)
    
    # Launch apscheduler service
    scheduler_process = subprocess.Popen(scheduler_cmd)

    print("\n----------------------------------------------------")
    print("[SUCCESS] Web Server running at: http://localhost:8000")
    print("[SUCCESS] Scheduler Service running in background")
    print("[INFO] Press Ctrl+C in this terminal to stop all services")
    print("----------------------------------------------------\n")

    try:
        while True:
            # Keep parent script running and check if main subprocesses crashed
            if web_process.poll() is not None:
                print("[WARNING] Web server stopped unexpectedly.")
                break
            if scheduler_process.poll() is not None:
                print("[WARNING] Scheduler service stopped unexpectedly.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n[INFO] Stopping all services...")
        web_process.terminate()
        scheduler_process.terminate()
        if update_process.poll() is None:
            update_process.terminate()
        
        # Wait for them to exit completely
        web_process.wait()
        scheduler_process.wait()
        if update_process.poll() is None:
            update_process.wait()
        print("[SUCCESS] Services stopped successfully.")

if __name__ == "__main__":
    run()