# Baut das Vite-Frontend und serviert den statischen Build per `vite preview`.
# Fuer taegliche Entwicklung ist `npm run dev` auf dem Host schneller (HMR) --
# dieser Service ist fuer einen "docker compose up"-Rundumschlag ohne lokale
# Node-Installation und fuers Testen vom Handy im lokalen Netz (siehe README
# "Vom Handy im lokalen Netz testen").

FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# VITE_API_BASE wird zur BUILD-Zeit ins Bundle eingebacken (import.meta.env,
# siehe src/api.js) -- nicht zur Laufzeit. Der Default passt fuer Zugriff vom
# selben Rechner; fuers Handy-Testen die LAN-IP des Host-Rechners uebergeben
# (docker compose liest sie aus der .env im Repo-Root).
ARG VITE_API_BASE=http://localhost:8000
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

EXPOSE 5173
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "5173"]
