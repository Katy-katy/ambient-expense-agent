FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn "google-adk[gcp]>=2.0.0,<3.0.0" google-cloud-aiplatform google-genai pydantic jinja2

COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
