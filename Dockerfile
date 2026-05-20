FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY detections ./detections
COPY scenarios ./scenarios
COPY telemetry ./telemetry
COPY runbooks ./runbooks
COPY configs ./configs
RUN python -m pip install --no-cache-dir .
EXPOSE 8787
CMD ["greynoc-dmz", "dashboard", "--host", "0.0.0.0", "--port", "8787"]
