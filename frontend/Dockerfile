# frontend/Dockerfile
FROM node:22.23.4-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.30.6-alpine
LABEL org.opencontainers.image.title="GANDAL-AI interface" \
      org.opencontainers.image.description="Interface du RAG navigation du projet GANDAL GI27" \
      org.opencontainers.image.authors="Felix NZIKO"
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
