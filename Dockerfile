FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Default command (can be overridden)
#CMD ["uvicorn", "health_check:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["python", "health_check.py"]

# Expose port for health check web service
EXPOSE 8000
