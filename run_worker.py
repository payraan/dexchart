print("DEBUG: Attempting to start run_worker.py...")
#!/usr/bin/env python3
import os
from celery import Celery
from config import Config

# This will start the Celery worker
if __name__ == "__main__":
    # Import tasks to register them
    from tasks import celery_app
    
    # Start worker with concurrency=2 (adjust based on your Railway plan)
    os.system("celery -A tasks worker --loglevel=info --concurrency=2")
