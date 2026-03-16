FROM node:20-alpine AS build

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
RUN npm run build

FROM nginx:1.27-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
COPY frontend/public/themes /usr/share/nginx/html/themes
RUN chmod -R 755 /usr/share/nginx/html \
    && find /usr/share/nginx/html/themes -type f -exec chmod 644 {} \; \
    && chown -R nginx:nginx /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
