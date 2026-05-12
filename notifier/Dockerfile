FROM python:3.13-alpine

WORKDIR /app

RUN pip install --no-cache-dir "psycopg[binary]==3.2.13"

COPY notifier.py /app/notifier.py

CMD ["python", "/app/notifier.py"]
