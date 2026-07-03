# SportsPoll frontend — static React build served by nginx, deployed to
# Cloud Run. VITE_API_BASE_URL is a Vite build-time env var (baked into the
# static JS bundle, not read at container runtime), so it must be passed as
# a build ARG pointing at the already-deployed API's Cloud Run URL — deploy
# the API service first, then this one with:
#   gcloud run deploy sportspoll-frontend --source frontend \
#     --build-arg VITE_API_BASE_URL=https://<api-service-url>

FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
