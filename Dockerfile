# Use official Python lightweight image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed for compiling certain packages if necessary
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and files
COPY src/ ./src/
COPY api/ ./api/
COPY models/ ./models/
COPY D:/KAWAH-PUTIH-SULPHUR-PROJECT/expanded_24H_all_data.csv ./expanded_24H_all_data.csv
# Fallback to look in local directory if path is mapped differently in docker context
COPY expanded_24H_all_data.csv* ./ 
COPY all_data_ts.csv ./

# Expose API port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Run FastAPI using Uvicorn
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
