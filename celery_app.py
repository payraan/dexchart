from celery import Celery
from config import Config

# Naming the app something unique and explicitly including the tasks module
# is the most reliable way to configure Celery.
celery_app = Celery('dexchart_worker',
                  broker=Config.REDIS_URL,
                  backend=Config.REDIS_URL,
                  include=['tasks'])

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)
