FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first
COPY requirements.txt .

# Install dependencies as ROOT (important)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create user AFTER installing packages
RUN useradd -m -u 1000 user

# Switch to user
USER user

# Copy app files
COPY --chown=user . .

# Run app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]