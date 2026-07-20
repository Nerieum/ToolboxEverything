# =====================================================
# Toolbox Everything — image Docker (multi-stage)
#
#   1. py-builder   : installe les deps Python dans /opt/venv
#   2. css-builder  : compile Tailwind (binaire Go standalone, pas de Node)
#   3. runtime      : image finale, zéro outil de build
# =====================================================
ARG TAILWIND_VERSION=4.3.3

# -----------------------------------------------------
# 1) Build des deps Python
# -----------------------------------------------------
FROM python:3.12-slim AS py-builder

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------
# 2) Build du CSS Tailwind
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
# 3) Image finale
# -----------------------------------------------------
FROM python:3.12-slim

LABEL maintainer="toolbox-everything"
LABEL description="Toolbox Everything - Une boite a outils web complete"
LABEL org.opencontainers.image.source="https://github.com/doalou/toolbox_everything"
LABEL org.opencontainers.image.documentation="https://github.com/doalou/toolbox_everything/README.md"

# FFmpeg est la seule dépendance système du runtime. Le healthcheck utilise
# urllib (stdlib), donc curl n'est plus nécessaire dans l'image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=py-builder /opt/venv /opt/venv
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
EXPOSE 8000

RUN groupadd -r toolbox && \
    useradd -r -g toolbox toolbox && \
    mkdir -p uploads/temp logs && \
    chown -R toolbox:toolbox /app
USER toolbox

# Une clé éphémère unique est créée au démarrage du conteneur si aucune clé
# persistante n'est fournie. Elle n'est ainsi jamais figée dans une couche.
CMD export SECRET_KEY="${SECRET_KEY:-$(python -c 'import secrets; print(secrets.token_hex(32))')}" && \
    exec gunicorn --bind 0.0.0.0:8000 --workers 4 --threads 2 --timeout 900 \
    --access-logfile - --error-logfile - run:app
