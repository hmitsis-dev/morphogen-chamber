FROM python:3.12-slim

WORKDIR /app
COPY receiver/requirements.txt ./receiver/requirements.txt
RUN pip install --no-cache-dir -r receiver/requirements.txt

COPY pulse/pulse.py ./pulse/pulse.py
COPY receiver/main.py ./receiver/main.py
COPY receiver/static ./receiver/static

ENV STATIC_DIR=/app/receiver/static
EXPOSE 8080
ENTRYPOINT ["python3", "receiver/main.py"]
