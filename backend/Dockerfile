# Use official Python lightweight image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed for compiling certain packages if necessary
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file (from root-based context build)
COPY backend/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and files
COPY backend/api/ ./api/
COPY backend/src/ ./src/
COPY backend/config.py ./config.py
COPY backend/models/ ./models/

# Copy datasets
COPY data/processed/expanded_24H_all_data.csv ./data/processed/expanded_24H_all_data.csv
COPY data/raw/all_data_ts.csv ./data/raw/all_data_ts.csv

# Expose API port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Run FastAPI using Uvicorn
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
