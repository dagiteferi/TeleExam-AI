FROM python:3.12-slim

# Install system dependencies, including redis-server
RUN apt-get update && apt-get install -y build-essential redis-server && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage caching
COPY requirements.txt .

# Install Python packages as root
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create non-root user and ensure they own the working directory
RUN useradd -m -u 1000 user && chown -R user:user /app
USER user

# Copy the rest of the code
COPY --chown=user . .

# Run Redis server in the background, then start FastAPI app
CMD ["bash", "-c", "redis-server & sleep 2 && uvicorn app.main:app --host 0.0.0.0 --port 7860"]