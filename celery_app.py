from celery import Celery

# Define the Celery app.
# The broker configuration will now be passed directly via the command line in the Procfile.
celery_app = Celery('dexchart_worker', include=['tasks'])
