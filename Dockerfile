FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

ARG CACHEBUST=1
RUN pip install --no-cache-dir -U "yt-dlp[default]" deno

COPY . .

ENV ENVIRONMENT=prod
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
