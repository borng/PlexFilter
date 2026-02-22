FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/plexfilter/ ./plexfilter/
COPY --from=frontend-build /app/frontend/dist ./static

ENV PLEXFILTER_DATABASE_PATH=/data/plexfilter.db
ENV PLEXFILTER_PLEXAUTOSKIP_JSON_PATH=/data/custom.json
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "plexfilter.main:app", "--host", "0.0.0.0", "--port", "8000"]
