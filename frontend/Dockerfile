FROM node:20-alpine

WORKDIR /app

ARG NPM_REGISTRY=https://registry.npmmirror.com
ENV npm_config_registry=${NPM_REGISTRY}
ENV npm_config_fetch_retries=5
ENV npm_config_fetch_retry_mintimeout=20000
ENV npm_config_fetch_retry_maxtimeout=120000

COPY frontend/package.json /app/frontend/package.json
WORKDIR /app/frontend
RUN npm install --prefer-offline --no-audit --no-fund

COPY frontend /app/frontend
WORKDIR /app/frontend

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
