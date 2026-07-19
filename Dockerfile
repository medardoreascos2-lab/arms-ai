FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN python -m pip install \
    --no-cache-dir \
    --upgrade pip \
    && python -m pip install \
    --no-cache-dir \
    -r requirements.txt

COPY backend ./backend
COPY docs ./docs

EXPOSE 8000

CMD [
    "python",
    "-m",
    "uvicorn",
    "backend.api.app:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8000"
]
