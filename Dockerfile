FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p runtime/telemetry \
    && chown -R appuser:appuser /app

USER appuser

ENTRYPOINT ["python", "run_local_test.py"]
CMD ["--mode", "smoke", "--scenario", "a"]
