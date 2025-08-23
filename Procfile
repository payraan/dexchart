web: uvicorn webhook_bot:app --host 0.0.0.0 --port $PORT --workers 1
worker: celery -A celery_app worker --loglevel=info -P eventlet --concurrency=5 -b "redis://${REDISUSER}:${REDISPASSWORD}@${REDISHOST}:${REDISPORT}" --result-backend "redis://${REDISUSER}:${REDISPASSWORD}@${REDISHOST}:${REDISPORT}"
