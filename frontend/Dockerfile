# ObRail Europe frontend image: React/Vite build then static serving
# via nginx (2 stages, so Node and node_modules are NOT shipped in the
# final image - only the compiled HTML/CSS/JS).
#
#   docker build -f frontend/Dockerfile -t obrail-frontend ./frontend

# --- Stage 1: build ------------------------------------------------------
FROM node:20-slim AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# VITE_API_URL is injected INTO the JavaScript at build time (Vite has
# no notion of a "runtime" environment variable on the browser side):
# that's why it's a build-arg rather than an environment variable of the
# final nginx container. Default value = the API published by
# docker-compose on port 8001 of the host machine, the one the BROWSER
# (not the other containers) needs to reach.
ARG VITE_API_URL=http://localhost:8001
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# --- Stage 2: static serving ---------------------------------------------
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# "127.0.0.1", not "localhost": BusyBox wget (this Alpine image) resolves
# "localhost" to the IPv6 loopback (::1) and does not fall back to IPv4,
# while nginx here only listens on 0.0.0.0 (IPv4) - using "localhost"
# made this healthcheck fail permanently despite the server actually
# working (verified: curl from the host on the published port always
# succeeded). Caught by manually inspecting `docker inspect`'s health
# log and testing both addresses directly inside the container.
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=5 \
    CMD wget -q -O- http://127.0.0.1/ || exit 1
