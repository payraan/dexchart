import os
from celery import Celery

# Step 1: Read the individual Redis components directly from the environment.
# This bypasses any issues with the pre-formatted REDIS_URL variable.
redis_host = os.getenv("REDISHOST")
redis_port = os.getenv("REDISPORT")
redis_user = os.getenv("REDISUSER", "default")
redis_password = os.getenv("REDISPASSWORD")

# Step 2: Check if all necessary components are available.
if not all([redis_host, redis_port, redis_password]):
    raise ValueError("CRITICAL: Redis connection components (REDISHOST, REDISPORT, REDISPASSWORD) are not fully set!")

# Step 3: Manually and safely construct the connection URL. This is the most reliable method.
clean_redis_url = f"redis://{redis_user}:{redis_password}@{redis_host}:{redis_port}"

print(f"INFO: Final Celery URL constructed: {clean_redis_url}")

# Step 4: Initialize Celery with our manually constructed, clean URL.
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
