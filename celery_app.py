import os
from celery import Celery
from config import Config

# Define the Celery application from this central file
celery_app = Celery('tasks', broker=Config.REDIS_URL, backend=Config.REDIS_URL)

# Automatically discover and register tasks from the 'tasks.py' file
celery_app.autodiscover_tasks(['tasks'])
