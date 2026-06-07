FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir -e .

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV PORT=7860
EXPOSE 7860

CMD ["python", "server.py"]
