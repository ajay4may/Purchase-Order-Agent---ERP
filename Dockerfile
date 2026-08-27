FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8088

WORKDIR /app
COPY requirements.lock pyproject.toml README.md ./
COPY app ./app
COPY schemas ./schemas

RUN pip install --no-cache-dir -r requirements.lock \
    && PYTHONDONTWRITEBYTECODE= python -m compileall -q app

EXPOSE 8088
CMD ["python", "-m", "app.main"]
