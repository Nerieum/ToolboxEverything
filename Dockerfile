# =====================================================
# Toolbox Everything — image Docker (multi-stage)
#
#   1. deno-bin     : fournit le runtime JS recommandé par yt-dlp
#   2. py-builder   : installe les deps Python dans /opt/venv
#   3. css-builder  : compile Tailwind (binaire Go standalone, pas de Node)
#   4. runtime      : image finale, zéro outil de build
# =====================================================
ARG TAILWIND_VERSION=4.3.3
ARG DENO_VERSION=2.9.5

# -----------------------------------------------------
# 1) Runtime JavaScript pour les challenges YouTube EJS
# -----------------------------------------------------
FROM denoland/deno:bin-${DENO_VERSION} AS deno-bin

# -----------------------------------------------------
# 2) Build des deps Python
# -----------------------------------------------------
FROM python:3.12-slim AS py-builder

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------
# 3) Build du CSS Tailwind
#    Même pipeline que le dev local : script Python + CLI standalone.
#    Le binaire est téléchargé dans ce stage, puis jeté.
# -----------------------------------------------------
FROM python:3.12-slim AS css-builder

ARG TAILWIND_VERSION
ENV TAILWIND_VERSION=${TAILWIND_VERSION}

WORKDIR /build
COPY scripts/tailwind.py ./scripts/tailwind.py
COPY tailwind.config.js ./
COPY app/static/css/input.css ./app/static/css/input.css
COPY app/templates ./app/templates
COPY app/static/js ./app/static/js
COPY app/services ./app/services

RUN python scripts/tailwind.py build && \
    python scripts/tailwind.py check

# -----------------------------------------------------
# 4) Image finale
# -----------------------------------------------------
FROM python:3.12-slim

LABEL maintainer="Association Nerieum"
LABEL description="Toolbox Everything - Une boite a outils web complete"
LABEL org.opencontainers.image.authors="Association Nerieum"
LABEL org.opencontainers.image.vendor="Association Nerieum"
LABEL org.opencontainers.image.source="https://github.com/Nerieum/ToolboxEverything"
LABEL org.opencontainers.image.documentation="https://github.com/Nerieum/ToolboxEverything/blob/main/README.md"

# FFmpeg est la seule dépendance installée via APT. Le healthcheck utilise
# urllib (stdlib), et Deno est copié depuis son image binaire officielle.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=py-builder /opt/venv /opt/venv
COPY --from=deno-bin /deno /usr/local/bin/deno
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY app ./app
COPY config.py run.py VERSION ./
# CSS Tailwind généré par le stage css-builder.
COPY --from=css-builder /build/app/static/css/tailwind.css /app/app/static/css/tailwind.css

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=run.py
ENV FLASK_ENV=production
ENV DOCKER_ENV=1
ENV HOME=/home/toolbox
EXPOSE 8000

RUN groupadd -r toolbox && \
    useradd -r -m -d /home/toolbox -g toolbox toolbox && \
    mkdir -p uploads/temp logs /home/toolbox/.cache/deno /var/lib/toolbox/yt-dlp && \
    chown -R toolbox:toolbox /app /home/toolbox /var/lib/toolbox
USER toolbox

# Une clé éphémère unique est créée au démarrage du conteneur si aucune clé
# persistante n'est fournie. Elle n'est ainsi jamais figée dans une couche.
CMD export SECRET_KEY="${SECRET_KEY:-$(python -c 'import secrets; print(secrets.token_hex(32))')}" && \
    exec gunicorn --bind 0.0.0.0:8000 --workers 4 --threads 2 --timeout 900 \
    --no-control-socket --access-logfile - --error-logfile - run:app
