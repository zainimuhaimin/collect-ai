# ── Stage 1: build bundle React/Vite ─────────────────────────────────────────
FROM node:24-alpine AS build

WORKDIR /app

# Salin manifest dulu (terpisah dari source) supaya layer `npm ci` ter-cache
# selama package.json/package-lock.json tidak berubah.
COPY package.json package-lock.json ./
# CATATAN: idealnya `npm ci` (reproducible, lebih cepat), TAPI package-lock.json
# saat ini tidak sinkron dengan package.json — `npm ci` gagal dengan
# "Missing: @emnapi/core@... from lock file". Selama lockfile belum di-refresh
# (`cd app/frontend && npm install`, lalu commit lockfile-nya), `npm install`
# adalah satu-satunya yang jalan. Setelah lockfile sinkron, ganti balik ke:
#   RUN npm ci
RUN npm install --no-audit --no-fund

COPY . .

# Vite meng-inline env ber-prefix VITE_ pada saat BUILD, bukan runtime — jadi
# nilainya harus masuk di sini sebagai ARG, tidak bisa lewat `environment:`
# di docker-compose. VITE_ENABLE_MSW=false: di image produksi frontend bicara
# ke backend asli lewat nginx, mock MSW tidak ikut dibundel.
ARG VITE_API_BASE_URL=/api
ARG VITE_ENABLE_MSW=false
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_ENABLE_MSW=$VITE_ENABLE_MSW

RUN npm run build


# ── Stage 2: sajikan lewat nginx ─────────────────────────────────────────────
FROM nginx:1.27-alpine

# Ditaruh di templates/ supaya entrypoint nginx menjalankan envsubst
# (mengisi ${SERVER_NAME}) lalu menulis hasilnya ke conf.d/default.conf.
COPY nginx/nginx.conf.template /etc/nginx/templates/default.conf.template

# Isi blok server yang dipakai bersama listener :80 dan :443.
COPY nginx/snippets/ /etc/nginx/snippets/

# CATATAN: nginx/tls.conf.template SENGAJA tidak di-COPY ke sini. Kalau ikut
# masuk ke templates/, nginx akan selalu mencari file sertifikat dan gagal
# start di environment yang tidak punya (mis. laptop). File itu di-bind-mount
# saat dibutuhkan lewat docker-compose.prod.yml.

# Hanya artefak hasil build yang ikut — tanpa node_modules, tanpa source.
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
