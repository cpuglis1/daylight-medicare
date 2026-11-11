# Exact image digest must be frozen after actual-target verification; this tag is
# portable development configuration, not a claim of a deployed/locked image.
FROM python:3.14.7-slim
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY src ./src
COPY migrations ./migrations
COPY config ./config
ENV PYTHONPATH=/app/src
USER 65532:65532
CMD ["python", "-m", "uvicorn", "daylight_data.api.app:build_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
