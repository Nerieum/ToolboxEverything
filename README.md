# Toolbox Everything

> Une boîte à outils web, modulaire et sans prise de tête : télécharger une vidéo (YouTube, Vimeo, Dailymotion, TikTok), convertir un média, bidouiller un QR code ou un hash, et manipuler des PDF sans quitter son navigateur.

Stack : **Flask + Tailwind**, tout en Docker, prêt à être posé derrière un reverse proxy.
Interface **sobre et utilitaire** (v2.0.1) : couche de tokens CSS, thème clair/sombre
piloté par variables, Fraunces self-hébergée et zéro dépendance front tierce au runtime.

Site public : <https://toolbox.doalo.fr>

Toolbox Everything est édité et exploité par l'**association Nerieum**.

![version](https://img.shields.io/badge/version-2.0.1-blue)
![python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![flask](https://img.shields.io/badge/flask-3.1-000000?logo=flask)
![license](https://img.shields.io/badge/license-MIT-green)

---

## Ce qu'il y a dedans

| Module | En deux mots |
|---|---|
| **Downloader vidéo / audio** | `yt-dlp` 2026.x, multi-plateformes (YouTube, Vimeo, Dailymotion, TikTok), fragments en parallèle, merge `bestvideo+bestaudio` via FFmpeg. |
| **Convertisseur Média** | Images (PNG, JPG, WebP, GIF, etc.) et vidéos (MP4, WebM, MKV, etc.) avec contrôle qualité mappé sur le CRF de FFmpeg. |
| **Outils Essentiels** | 13 outils 100% client-side : QR codes, mots de passe (+ passphrase), SHA-1/256/384/512, Base64, JSON formatter, palettes, timestamps, UUID v4/v7, JWT decoder, regex tester, URL encoder, Lorem Ipsum, diff. Rien n'est envoyé au serveur. |
| **Outils PDF** | 150+ opérations via **Stirling PDF** embarqué (fusion, split, OCR, compression, signature, watermark). Instance **amnésique** : `/configs`, `/logs` et `/tmp` en RAM, zéro analytics, nettoyage temp toutes les 5 min. |
| **Healthcheck** | Un seul `/health` pour savoir si `yt-dlp`, `ffmpeg` et `stirling-pdf` répondent. |

---

## Démarrage rapide

### Avec Docker Compose (recommandé)

Un **unique** `compose.yml` couvre les deux modes de déploiement, choix via `TOOLBOX_IMAGE` :

```bash
git clone https://github.com/Nerieum/ToolboxEverything.git
cd toolbox_everything
cp env.example .env          # édite au moins SECRET_KEY
docker compose up -d --build # build local (dev / CI)
```

Ou en prod avec l'image publique GHCR :

```bash
export TOOLBOX_IMAGE=ghcr.io/nerieum/toolboxeverything:2.0.1
docker compose pull && docker compose up -d
```

Une fois démarré :

- Toolbox → <http://localhost:8000>
- Stirling PDF (iframe) → <http://localhost:8080>
- LibreSpeed (iframe) → <http://localhost:8081>

### En local (sans Docker)

Python **3.12** est la version de référence du projet.

```bash
python -m venv venv
# Linux / macOS
source venv/bin/activate
# Windows
# venv\Scripts\activate

pip install -r requirements.txt
make tailwind-build          # build CSS (télécharge le binaire au premier run)
python run.py --dev
```

> Les outils PDF et Speedtest nécessitent leurs services côté serveur. Voir la section Configuration ou lance `docker compose up -d`.
> Le rate limiter tombe sur `memory://` si aucun Redis n'est accessible. OK en dev.

Le service Stirling PDF fourni par `compose.yml` est volontairement amnésique :
ses répertoires de travail, profils LibreOffice, configuration et logs sont
montés en RAM (`tmpfs`) et aucun volume persistant ne lui est attaché. Les
documents et toute configuration générée disparaissent donc au redémarrage du
conteneur. La couche système reste inscriptible uniquement pour que le script
d'initialisation officiel de Stirling puisse créer ses liens internes.

---

## Configuration

Tout se passe dans `.env` (copié depuis `env.example`) :

| Variable | Rôle | Défaut |
|---|---|---|
| `SECRET_KEY` | Clé Flask, **à fixer** en prod | auto-générée si absente |
| `FLASK_ENV` | `development` ou `production` | `production` |
| `MAX_CONTENT_LENGTH` | Taille max des uploads (octets) | `536870912` (512 MB) |
| `FFMPEG_PATH` | Chemin explicite vers FFmpeg | auto-détecté (`shutil.which`) |
| `YTDLP_COOKIES_FILE` | Fichier Netscape de cookies pour yt-dlp | désactivé |
| `YTDLP_COOKIES_STATE_DIR` | Cookie jar inscriptible et persistant | `/var/lib/toolbox/yt-dlp` |
| `YTDLP_USER_AGENT` | User-Agent associé aux cookies yt-dlp | défaut yt-dlp |
| `YTDLP_DENO_PATH` | Chemin du runtime Deno | auto-détecté (`shutil.which`) |
| `STIRLING_PDF_URL` | URL **interne** de Stirling PDF (healthcheck serveur) | `http://stirling-pdf:8080` |
| `STIRLING_PDF_PUBLIC_URL` | URL **publique** utilisée par l'iframe (navigateur) | `http://localhost:8080` |
| `LIBRESPEED_URL` | URL **interne** de LibreSpeed (healthcheck serveur) | `http://librespeed` |
| `LIBRESPEED_PUBLIC_URL` | URL **publique** utilisée par l'iframe (navigateur) | `http://localhost:8081` |
| `RATELIMIT_STORAGE_URI` | Backend du rate limiter (Redis en prod) | `redis://redis:6379/0` |
| `TOOLBOX_IMAGE` | Image Docker à tirer depuis GHCR | `ghcr.io/nerieum/toolboxeverything:2.0.1` |
| `TOOLBOX_PORT` / `STIRLING_PORT` / `LIBRESPEED_PORT` | Ports hôte exposés | `8000` / `8080` / `8081` |

### YouTube : Deno et authentification

L'image Docker contient déjà Deno et `yt-dlp-ejs`. Ils permettent à yt-dlp de
résoudre les challenges JavaScript de YouTube et ne demandent aucune
configuration.

Un fichier de cookies est uniquement nécessaire lorsque YouTube répond
« Sign in to confirm you're not a bot ». Le `.env` contient alors le chemin du
fichier, jamais les cookies eux-mêmes ni un token.

#### Préparer le fichier de cookies

1. Ouvrir une fenêtre privée, puis se connecter avec un compte YouTube dédié.
2. Dans le même onglet, ouvrir `https://www.youtube.com/robots.txt`.
3. Exporter les cookies `youtube.com` au format Netscape avec
   **Get cookies.txt LOCALLY** (Chrome/Chromium) ou **cookies.txt** (Firefox).
4. Fermer la fenêtre privée et ne plus utiliser cette session dans le navigateur.

Les liens des extensions et les précautions à suivre sont maintenus dans la
[documentation officielle yt-dlp](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies).
Ne jamais utiliser l'ancienne extension Chrome **Get cookies.txt** sans
« LOCALLY », signalée comme malveillante par yt-dlp.

Déposer ensuite le fichier à la racine du projet :

```bash
install -d -m 700 secrets
install -m 644 /path/to/youtube-cookies.txt secrets/youtube-cookies.txt
```

Le dossier privé protège le fichier sur l'hôte. Le mode `644` permet au
processus non-root du conteneur de le lire ; le montage Docker reste en lecture
seule. Pour laisser yt-dlp actualiser son cookie jar sans modifier le secret,
l'application initialise une copie inscriptible dans le volume Docker
`toolbox_ytdlp_state`, puis conserve les mises à jour reçues de YouTube. Les
workers partagent ce jar sous verrou. Le remplacement du fichier source
réinitialise automatiquement la copie grâce à son empreinte SHA-256. Le dossier
`secrets/` est exclu de Git et du contexte de build.

#### Activer les cookies

Dans `.env` :

```dotenv
YTDLP_COOKIES_FILE=/run/secrets/youtube-cookies.txt
YTDLP_COOKIES_STATE_DIR=/var/lib/toolbox/yt-dlp
```

Dans le service `toolbox` de `compose.yml` :

```yaml
volumes:
  - ./secrets/youtube-cookies.txt:/run/secrets/youtube-cookies.txt:ro
```

Recréer le service puis tester la session :

```bash
docker compose up -d --force-recreate toolbox
docker compose exec toolbox yt-dlp \
  --cookies /run/secrets/youtube-cookies.txt \
  --simulate --print title 'https://www.youtube.com/watch?v=BaW_jenozKc'
```

Si YouTube redemande une connexion, refaire l'export et remplacer le fichier.
Un PO Token est un mécanisme différent et n'est pas configuré par ce projet ;
le [guide yt-dlp](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide) ne devient
pertinent que si l'erreur mentionne explicitement un PO Token.

---

## Versioning et images GHCR

La version de référence est `VERSION`. Pour la v2.0.1, elle alimente :

- La version affichée dans le footer et `/health`.
- Les tags locaux générés par `make docker-build`.
- Le workflow GitHub Actions qui publie l'image sur GHCR.

Images publiées :

```bash
ghcr.io/nerieum/toolboxeverything:2.0.1
ghcr.io/nerieum/toolboxeverything:2.0
ghcr.io/nerieum/toolboxeverything:latest
```

Règle de release :

1. Mettre à jour `VERSION`.
2. Reporter la version dans le badge README, les exemples GHCR et `CHANGELOG.md`.
3. Merger sur `main`.
4. Le workflow Docker détecte le bump de `VERSION` sur ce push et publie les tags
   `X.Y.Z` (immuable), `X.Y` (dernière correction de la branche mineure) et
   `latest`. Les commits sans bump, ainsi que le cron nocturne, ne réécrivent que
   `latest`.
5. Le workflow `Release tag` crée en parallèle le tag Git `vX.Y.Z` (marqueur d'historique).

Exemple pour publier une nouvelle version :

```bash
echo 2.0.2 > VERSION
git add VERSION CHANGELOG.md README.md
git commit -m "Release 2.0.2"
git push origin main
```

---

## Sécurité

La couche exposée est sérieusement durcie (voir `CHANGELOG.md` pour le détail) :

- **CSP stricte avec nonce par requête**, `frame-ancestors 'none'`, `object-src 'none'`,
  Permissions-Policy verrouillée, HSTS conditionnel sur HTTPS.
- **Rate limiter Redis** (Flask-Limiter) sur les routes coûteuses : 3/min sur
  `/downloader/download`, 10/min sur `/media/convert`, etc.
- **Validation des uploads par magic bytes** (stdlib only, pas de `libmagic`),
  plafond batch 20 fichiers / 200 MB, garde anti-bombe Pillow (50 Mpx).
- **Whitelist yt-dlp** : YouTube, Vimeo, Dailymotion, TikTok uniquement.
  Les schemes `file://`, `ftp://`, `javascript:` sont explicitement bloqués.
- **Zéro CDN pour les assets critiques** : Tailwind est compilé localement
  (CLI standalone, sortie ~15 KB minifiée), Font Awesome rapatrié en
  `app/static/vendor/`, seul `qrcode-generator` reste en CDN avec SRI SHA-384
  obligatoire (enforcé par le modèle `ExternalScript`).

Tests dédiés dans `tests/test_security.py`.

---

## Structure du projet

```
toolbox_everything/
├── app/
│   ├── core/                     # api (marqueur JSON), files, rate_limit, security_headers, uploads
│   ├── services/
│   │   ├── main.py               # Factory Flask (logging, compress, /health, errors)
│   │   ├── _embedded.py          # Helper iframe partagé (Stirling / LibreSpeed)
│   │   ├── downloader/           # yt-dlp (multi-plateformes)
│   │   ├── media_converter/      # FFmpeg / Pillow
│   │   ├── essentials/           # 13 outils client-side (registry auto-enregistrée)
│   │   ├── pdf_tools/            # Iframe Stirling PDF + /pdf/status
│   │   └── speedtest/            # Iframe LibreSpeed + /speedtest/status
│   ├── static/
│   │   ├── css/style.css         # Design system (tokens :root/.dark, composants)
│   │   ├── css/input.css         # Source Tailwind → build vers tailwind.css
│   │   ├── vendor/fontawesome/   # Font Awesome local (plus de CDN)
│   │   ├── vendor/fonts/         # Fraunces (variable woff2, OFL) self-hébergée
│   │   └── js/                   # JS applicatif (main.js, media.js) + /essentials/*.js
│   └── templates/                # Jinja2 (base.html, _macros.html, errors/, ...)
├── tests/                        # pytest (111 tests)
├── config.py                     # Configuration centralisée (source unique des limites)
├── pyproject.toml                # Config outillage : ruff + black + pytest + coverage
├── tailwind.config.js            # Config Tailwind (purge, couleurs, animations)
├── run.py                        # CLI + cible Gunicorn (`run:app`)
├── Dockerfile                    # Multi-stage : py-builder + css-builder + runtime
├── compose.yml                   # Toolbox + Stirling PDF + LibreSpeed + Redis
├── requirements.txt              # Runtime (audité, 0 dépendance morte)
├── requirements-dev.txt          # Dev (pytest, ruff, black, bandit, pip-audit)
├── Makefile                      # setup, dev, test, lint, tailwind-*, docker-*
└── CHANGELOG.md
```

---

## Développement

```bash
make setup             # .env + SECRET_KEY + dépendances
make tailwind-install  # télécharge le binaire Tailwind CLI (une fois)
make tailwind-build    # build CSS minifié
make tailwind-watch    # build en continu (pour le dev CSS)
make dev               # python run.py --dev sur :8000
make test              # pytest (111 tests)
make test-cov          # pytest + couverture
make lint              # ruff check
make format            # ruff --fix + black
make docker-build      # construit les tags locaux et GHCR depuis VERSION
```

Bannière ASCII au boot (dev uniquement), logs rotatifs dans `logs/toolbox.log` (5 MB × 5).

---

## Endpoints principaux

| Route | Rôle |
|---|---|
| `GET /` | Accueil / dashboard |
| `GET /downloader/` | Téléchargeur vidéo / audio (YouTube, Vimeo, Dailymotion, TikTok) |
| `GET /downloader/info?url=...` | Métadonnées vidéo (JSON, 20/min) |
| `POST /downloader/download` | Téléchargement (JSON in, fichier out, 3/min) |
| `GET /media/` | Convertisseur média |
| `GET /essentials/` | Outils essentiels |
| `GET /pdf/` | Outils PDF (iframe Stirling) |
| `GET /pdf/status` | Statut JSON de Stirling PDF |
| `GET /speedtest/` | Speedtest (iframe LibreSpeed) |
| `GET /speedtest/status` | Statut JSON de LibreSpeed |
| `GET /health` | Healthcheck JSON (version, yt-dlp, ffmpeg, stirling, librespeed) |
| `GET /youtube/*` | Redirection 301/308 → `/downloader/*` (compat ascendante) |

---

## Licence

[MIT](LICENSE).
