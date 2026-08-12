FROM python:3.12-slim

WORKDIR /app
COPY pulse/pulse.py ./pulse/pulse.py
COPY sender/main.py ./sender/main.py

ENTRYPOINT ["python3", "sender/main.py"]
