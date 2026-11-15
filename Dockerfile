FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && (pip install --no-cache-dir --prefer-binary TgCrypto==1.2.5 || echo "WARNING: TgCrypto unavailable; Pyrogram pure-Python crypto fallback will be used")
COPY . .
CMD ["python", "bot.py"]
