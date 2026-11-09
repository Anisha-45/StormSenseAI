FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
# data/ is mounted as a volume (see docker-compose.yml) so raw files and the database persist
ENV STORMSENSE_ROOT=/srv
EXPOSE 8000
CMD ["sh", "-c", "python -m app.cli process && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
