FROM python:3.12-slim

WORKDIR /app

# Non-root kullanici (BUG-19)
RUN groupadd --system app && useradd --system --gid app --create-home app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY config ./config

RUN chown -R app:app /app
USER app

EXPOSE 8000

# Uretim: --reload YOK. Gelistirme icin docker-compose.yml komutu override eder.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
