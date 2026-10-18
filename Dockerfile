FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Moscow

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/
COPY main.py ./

RUN mkdir -p /app/data

EXPOSE 8080

CMD ["python", "main.py"]
