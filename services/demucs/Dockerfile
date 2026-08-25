# services/demucs/Dockerfile
FROM python:3.10-slim-bookworm

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y ffmpeg git curl && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Copy your code
COPY . .

EXPOSE 8000
CMD ["uvicorn","demucs_runner:app","--host","0.0.0.0","--port","8000"]
