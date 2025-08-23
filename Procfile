web: uvicorn webhook_bot:app --host 0.0.0.0 --port $PORT --workers 1
worker: celery -A celery_app worker --loglevel=info -P eventlet --concurrency=5 --broker="redis://${REDISUSER}:${REDISPASSWORD}@${REDISHOST}:${REDISPORT}"
