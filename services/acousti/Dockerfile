FROM python:3.10-slim-bookworm

# Set working directory
WORKDIR /app

# Install system dependencies for audio processing and fingerprinting
RUN apt-get update && \
    apt-get install -y ffmpeg libchromaprint-tools gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*





# Copy Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt



# Copy app code
COPY . .

# Run your fingerprint processor

EXPOSE 8000
CMD ["uvicorn","acousti_runner:app","--host","0.0.0.0","--port","8000"]
