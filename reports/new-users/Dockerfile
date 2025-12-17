FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities
COPY shared/ /app/shared/

# Copy application
COPY main.py .

# Set environment
ENV PYTHONUNBUFFERED=1

# Run with gunicorn for production
CMD exec gunicorn --bind :$PORT --workers 1 --threads 2 --timeout 120 main:app
