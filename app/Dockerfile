FROM python:3.12-slim

WORKDIR /srv

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY static/ ./static/

ENV STATIC_DIR=/srv/static
EXPOSE 8080

CMD ["python3", "app/main.py"]
