import os
from celery import Celery

# Step 1: Read individual Redis components directly from the environment.
redis_host = os.getenv("REDISHOST")
redis_port = os.getenv("REDISPORT")
redis_user = os.getenv("REDISUSER", "default")
redis_password = os.getenv("REDISPASSWORD")

# Step 2: Critical check for components.
if not all([redis_host, redis_port, redis_password]):
    raise ValueError("CRITICAL: Redis connection components (REDISHOST, REDISPORT, REDISPASSWORD) are not fully set!")

# Step 3: Manually and safely construct the connection URL.
clean_redis_url = f"redis://{redis_user}:{redis_password}@{redis_host}:{redis_port}"

print(f"INFO: Clean Redis URL constructed: {clean_redis_url}")

# Step 4: Initialize the Celery app WITHOUT broker settings initially.
celery_app = Celery('dexchart_worker', include=['tasks'])

# Step 5: Forcefully update the configuration AFTER initialization.
# This overrides any incorrect settings Celery might have loaded automatically.
celery_app.conf.update(
    broker_url=clean_redis_url,
    result_backend=clean_redis_url,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)
