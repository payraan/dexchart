import os
from celery import Celery

# Step 1: Read the REDIS_URL directly from the environment, bypassing config.py
raw_redis_url = os.getenv("REDIS_URL")

# Step 2: Critical check and cleanup
if not raw_redis_url:
    raise ValueError("CRITICAL ERROR: REDIS_URL is not set in the environment!")

# Clean the URL to remove any trailing slashes, which is the root cause of our problem.
clean_redis_url = raw_redis_url.rstrip('/')

print(f"INFO: Initializing Celery with CLEANED broker URL: {clean_redis_url}")

# Step 3: Initialize Celery with the cleaned, guaranteed-correct URL.
celery_app = Celery('dexchart_worker',
                  broker=clean_redis_url,
                  backend=clean_redis_url,
                  include=['tasks'])

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)
