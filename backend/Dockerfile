# Build-Kontext ist das Repo-Root (siehe docker-compose.yml: context: .),
# damit dieses Image sowohl backend/ als auch sim/ einbinden kann.

FROM python:3.12-slim

WORKDIR /srv

COPY backend/requirements.txt ./
# requirements.txt enthaelt `-e ../sim` fuer die Host-Entwicklung -- dieser
# Pfad existiert im Build-Kontext (Repo-Root) nicht. Zeile rausfiltern, die
# Sim-Engine wird gleich separat aus /sim installiert.
RUN grep -v '^-e ' requirements.txt > requirements.docker.txt \
    && pip install --no-cache-dir -r requirements.docker.txt

# Sim-Engine als editable Package mitbauen
COPY sim /sim
RUN pip install --no-cache-dir -e /sim

COPY backend/. .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
