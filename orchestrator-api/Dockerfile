FROM python:3.10-slim-bookworm

WORKDIR /app


RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
# Copy Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt



# Copy app code
COPY . .

EXPOSE 8000
CMD ["uvicorn","orchestrator_runner:app","--host","0.0.0.0","--port","8000"]
