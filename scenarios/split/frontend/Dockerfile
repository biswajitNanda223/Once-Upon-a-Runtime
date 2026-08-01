FROM node:20-bookworm-slim AS web
WORKDIR /src
COPY package*.json ./
RUN npm ci
COPY index.html tsconfig.json ./
COPY src ./src
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY proxy.py ./
COPY --from=web /src/static ./static
USER 65532
EXPOSE 8000
CMD ["uvicorn", "proxy:app", "--host", "0.0.0.0", "--port", "8000"]

