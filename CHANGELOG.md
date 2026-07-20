# Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Versionnage Sémantique](https://semver.org/lang/fr/).

---

## [2.0.0] - 2026-07-19

Refonte de fond en comble sur trois fronts (design, backend, outillage), à
périmètre fonctionnel constant : mêmes URLs, mêmes routes, même contrat
`/health`, même setup Docker.

### Design éditorial

- **Couche de tokens CSS** : `style.css` réécrit autour de custom properties
  (`:root` / `.dark`). Le thème sombre ne redéfinit que les variables — fin des
  dizaines de règles `.dark .composant` dupliquées et des littéraux magiques.
- **Identité utilitaire** : police display **Fraunces** (variable, OFL)
  self-hébergée (`app/static/vendor/fonts/`) réservée aux titres identitaires,
  typographie d'interface sans-serif, filets nets et aplats. L'accueil associe
  une couverture éditoriale asymétrique à un établi continu de cinq ateliers et
  un répertoire direct des treize essentiels, sans grille de cartes flottantes.
- **Logo d'origine conservé** : le symbole historique reste l'élément de marque
  principal ; la refonte du shell ne le remplace pas.
- **Bug wordmark corrigé** : « Toolbox Everything » n'est plus blanc-sur-blanc en
  thème clair (encre + accent, lisible dans les deux thèmes).
- **Palette du logo retrouvée** : fusion des deux bleus « primaires » historiques
  en un accent fonctionnel unique, puis réemploi mesuré du bleu, du rose et de
  leur violet intermédiaire comme repères de familles. Pas d'arc-en-ciel par outil
  ni d'aplats décoratifs : la couleur facilite l'orientation et les interactions.
- **Voix et motif de marque** : microcopie de l'accueil directe, signature « Tout
  sous la main » et petits losanges dérivés du symbole historique. Les compartiments
  colorés restent plats, jointifs et sans appels à l'action répétés.
- **Toasts unifiés** : une seule implémentation (`main.js`, composant `.toast`) au
  lieu de trois. Le script inline de la page média est extrait vers `media.js`.
- **Pages d'erreur** : 400/404/405/429/500 alignées sur le design system.
- **Navigation simplifiée** : fin de la capsule de navigation et de l'onglet actif
  en aplat ; état courant signalé par un filet d'accent.
- **Contenu recentré sur l'usage** : suppression du bloc marketing générique
  « Pourquoi utiliser nos outils ? » sur les six pages principales.
- **PDF et Speedtest peaufinés** : en-tête de service commun, statut joignable
  annoncé en texte, chargement d'iframe maîtrisé, ouverture externe explicite et
  véritable panneau d'exploitation lorsque Stirling PDF ou LibreSpeed est arrêté
  (capacités, procédure guidée et commande dédiée).
- **Breakpoints unifiés** et macro Jinja `home_tool` (`_macros.html`) pour l'accueil.

### Backend (consolidation, iso-fonctionnel)

- **Code mort supprimé** : `app/services/common/utils.py`, `media_converter/
  task_manager.py`, la classe `ResourceManager` et `app/core/exceptions.py`
  (hiérarchie jamais levée), plus `mediaConverter.js` / `mediaManager.js`.
- **Système d'erreurs unique** : la factory gère `HTTPException`/`Exception` ; la
  détection JSON passe par un marqueur `@json_endpoint` porté par les vues (fin de
  la liste de préfixes d'URL en dur).
- **Source unique** : un seul sanitizer (`app/core/files.py`), les limites d'upload
  dérivent de `config.Config`, FFmpeg résolu une seule fois (`app.config`).
- **pdf_tools / speedtest** : logique iframe factorisée dans `app/services/_embedded.py`.
- **Corrections** : `/downloader/download` valide la requête (400) avant la
  capacité FFmpeg (500) ; `quality` non numérique renvoie 400 (au lieu de 500) ;
  message de timeout FFmpeg corrigé (180 s, plus « 10 minutes ») ; double
  `from_object` de config supprimé ; prints diagnostics ASCII-safe (console Windows).
- **Conversion média allégée** : les images simples sont traitées directement
  en mémoire, sans aller-retour disque ; les ZIP de batch basculent sur disque
  au-delà de 16 Mio, avec extensions et noms de fichiers normalisés.
- **Démarrage simplifié** : `python run.py` ne construit plus deux applications
  Flask et les chemins/limites d'une configuration personnalisée ne sont plus
  écrasés par les valeurs par défaut.

### Outillage, CI, tests

- **`pyproject.toml`** : config centralisée **ruff** (lint + imports) + **black** +
  **pytest** + **coverage**, longueur de ligne unique (100). `.flake8` et
  `pytest.ini` supprimés. `isort==7.1.0` fantôme retiré de `requirements-dev`.
- **CI** : build Tailwind avant les tests, `ruff` + `black --check` (versions
  alignées CI/dev), couverture activée.
- **Dépendances actualisées** : neuf paquets Python montés sur leurs dernières
  versions stables (dont redis-py 8, Pillow 12.3, yt-dlp 2026.7 et gunicorn 26),
  `qrcode-generator` 2.0.4 avec nouveau SRI, Font Awesome 7.3.1, Redis 8.8.0 et
  actions GitHub à jour.
- **Tailwind 4.3** : migration du pipeline standalone vers la configuration CSS
  v4 (`@config`, `@source`) et ajout d'un marqueur de version pour retélécharger
  automatiquement le bon binaire lors d'un bump (4.3.3).
- **Tags GHCR immuables** : les tags de version `X.Y.Z` / `X.Y` ne sont republiés
  que lors d'un vrai bump de `VERSION` (ou sur tag Git) ; le cron nocturne et les
  commits sans bump ne réécrivent plus que `latest`.
- **Tests** : 111 au total (couverture ajoutée sur `/media/convert` & `/batch`, la
  branche configurée PDF/speedtest, HSTS, le sanitizer). `.gitignore` durci contre
  les `*.pyc.<pid>` orphelins.
- **CSS nettoyé** : fusion des trois générations successives de l'accueil et des
  deux variantes des pages de service ; `style.css` passe de 72 à 62 Kio sans
  modifier le rendu desktop/mobile.

### Versioning, publication & Docker

- **Source de version unique** : `VERSION` est la seule source applicative ;
  `APP_VERSION` est retiré de `.env`, `env.example`, `compose.yml` et du runtime
  Docker.
- **Publication GHCR** : les exemples de production et le `compose.yml` pointent
  sur `ghcr.io/doalou/toolbox_everything`. Workflow Docker unifié (suppression du
  doublon `.github/workflows/docker-image.yml`) et signature cosign retirée (fin
  des artefacts parasites `sha256-...sig`).
- **Contrôle release** : le workflow refuse un tag Git `vX.Y.Z` qui ne correspond
  pas au contenu de `VERSION` ; le workflow `Release tag` crée automatiquement
  `vX.Y.Z` sur `main`.
- **Makefile & Python 3.12** : `docker-build` lit `VERSION` (image locale + GHCR) ;
  ajout de `.python-version`, plus de `python3` hardcodé.
- **Image Docker réduite** : contexte de copie ciblé, suppression des compilateurs,
  de `curl`, des upgrades APT au build et de la clé secrète figée dans une couche.
- **Stirling PDF amnésique** : image 2.14.2 verrouillée, aucun volume Docker et
  tous les emplacements pouvant contenir des données (`/configs`, `/logs`,
  `/customFiles`, profil utilisateur, `/pipeline`, `/storage`, `/tmp`) montés en
  RAM. Le stockage, le partage, les comptes, l'audit et la télémétrie restent
  désactivés.

### Interface (socle consolidé)

- **Shell JavaScript extrait** : thème et navigation mobile déplacés du template
  `base.html` vers `shell.js`, chargé localement avec `defer`.
- **Assets versionnés** : CSS, JavaScript et logo reçoivent une empreinte de contenu
  en query string pour éviter le mélange entre un HTML neuf et des assets en cache,
  y compris pendant le développement d'une même version.
- **Switch clair/sombre** : lecture et écriture `localStorage` protégées, icônes
  soleil/lune gérées par CSS dédié, `aria-pressed` synchronisé et `theme-color`
  mis à jour au changement de thème.
- **Menu mobile** : conflit `lg:hidden` / breakpoint custom supprimé — hamburger
  et panneau au même seuil responsive `1180px`.

---

## [1.3.1] - 2026-04-25

> Cette release consolide trois chantiers menés sur le même cycle : refonte
> complète du module **Essentials** (architecture sous-blueprints + 100%
> client-side), durcissement **sécurité** (CSP/nonces, rate limiter Redis,
> validation des uploads par magic bytes), et rename `youtube_downloader` →
> `downloader` avec branding adaptatif multi-plateformes. Elle ajoute aussi
> LibreSpeed et un gros polish responsive.

### Renommé : `youtube_downloader` → `downloader`

Le module historiquement nommé d'après YouTube accepte désormais YouTube,
Vimeo, Dailymotion et TikTok. Le nom collait mal — d'où le rename.

- **Package Python** : `app/services/youtube_downloader/` → `app/services/downloader/`.
  Blueprint `youtube` → `downloader`. Fonction `youtube_bp` → `downloader_bp`.
  L'exception `YouTubeDownloadError` devient `DownloaderError`
  (`error_code = "DOWNLOADER_ERROR"`).
- **URL de service** : `/youtube/*` → `/downloader/*`. La nav (desktop + mobile),
  la home, les badges et les tests pointent désormais sur les nouvelles routes.
- **Compat ascendante** : `/youtube`, `/youtube/`, `/youtube/<path>` renvoient
  un **301 / 308 Permanent Redirect** vers leur équivalent `/downloader/*`.
  Les liens externes existants restent valides (et `308` préserve la méthode
  HTTP donc `POST /youtube/download` continue de fonctionner).
- **Variables orphelines retirées** : `YOUTUBE_DOWNLOAD_FOLDER` (jamais utilisé,
  les téléchargements passent par `tempfile.mkdtemp` + `after_this_request`)
  et `YOUTUBE_MAX_DURATION` (jamais lue par le code) supprimées de `config.py`,
  `env.example` et `README.md`. Le dossier `uploads/temp_youtube/` du Dockerfile
  également retiré.

### Refonte UI : page `/downloader/` (ex `/youtube/`)

- Identité visuelle **adaptative selon la plateforme** détectée dans l'URL
  (icône + couleur d'accent : YouTube rouge, Vimeo cyan, Dailymotion bleu,
  TikTok rose/noir). Disparition du rouge YouTube fixé en dur.
- **Détection client** : `detectPlatform(url)` côté JS (en plus du whitelisting
  serveur strict). L'icône Font Awesome de la pill bascule en live.
- **Mini-historique localStorage** des 5 dernières URLs analysées avec succès.
  Stocké uniquement côté navigateur, **jamais transmis au serveur**, effaçable
  d'un clic.
- **Indicateur de quota live** : lecture des headers `X-RateLimit-Remaining` /
  `X-RateLimit-Limit` de Flask-Limiter, surlignage ambre quand il reste ≤ 3
  requêtes.
- **Barre de progression animée** dégradé multicolore (cohérent avec le ton
  multi-plateformes), ré-coloré dynamiquement selon la plateforme détectée.
- **Nouveau JS dédié** : `app/static/js/downloader.js` (~330 lignes), zéro
  dépendance externe, chargé en `defer` avec nonce CSP.

### Polish léger : page `/essentials/`

- Sous-titre dynamique (`{{ tools|length }} micro-outils`).
- Trois badges discrets sous le hero : « 100% local », « Aucun appel serveur »,
  « Open source ».
- Attribut `data-category` ajouté aux cartes pour pouvoir filtrer plus tard
  côté client sans casser le markup.
- Carte **UUID generator** corrigée dans la grille des outils essentiels :
  le fond de couleur de l'icône est bien rendu comme les autres outils.

### Interface et responsive

- **Titres d'onglet professionnalisés** : suppression des tirets longs dans les
  `<title>` et format homogène `Page | Toolbox Everything` sur les pages
  principales, les outils Essentials et les erreurs.
- **Header** : branding ajusté avec `Toolbox` en dégradé `#5c6ff4` vers
  `#e870c2`, et `Everything` en blanc.
- **Switch clair/sombre réparé** : suppression des handlers inline bloqués par
  la CSP, branchement via listeners JS nonce-safe.
- **Menu mobile corrigé** : le bouton hamburger ne s'affiche plus en desktop,
  et le sous-menu mobile Essentials fonctionne sans `onclick` inline.
- **Nettoyage des textes visibles** : retrait des formulations trop génériques,
  des ellipses et des tirets longs sur les pages principales et les outils.
- **Responsive** : header desktop repoussé à 1180px, grille d'accueil dédiée,
  iframes PDF/Speedtest adaptées au mobile, grilles de formulaires Essentials
  stabilisées sur petits écrans.
- **Accueil** : ajout d'un CTA **Speedtest** vers `/speedtest/` avec état
  `Tester` / `Configurer` selon la configuration LibreSpeed.

### Sécurité (lot majeur)

Toutes les protections ci-dessous sont **effectivement branchées** sur les routes
et couvertes par une suite de tests dédiée (`tests/test_security.py`, 37 tests).

- **CSP avec nonce par requête** (`app/core/security_headers.py`) : aucun script
  inline n'est accepté sans un `nonce` cryptographique régénéré à chaque
  requête. La CSP inclut également `frame-ancestors 'none'`, `object-src 'none'`,
  `base-uri 'self'`, `form-action 'self'`, `worker-src 'self' blob:` et
  `upgrade-insecure-requests`. Les domaines des iframes Stirling PDF et
  LibreSpeed sont whitelistés dynamiquement via `STIRLING_PDF_PUBLIC_URL` et
  `LIBRESPEED_PUBLIC_URL`.
- **Headers HTTP complets** : `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: strict-origin-when-cross-origin`, `Cross-Origin-Opener-Policy: same-origin`,
  `Cross-Origin-Resource-Policy: same-origin`, `Permissions-Policy` désactivant
  tout ce que l'app n'utilise pas (caméra, micro, géoloc, USB, paiement, MIDI, etc.),
  `Strict-Transport-Security` activé automatiquement quand la requête est en HTTPS.
- **Rate limiter branché** (`Flask-Limiter 4.1.1` + **Redis 7.4**) :
  - `/downloader/info` : 20/min
  - `/downloader/download` : 3/min et 30/h
  - `/media/convert` : 10/min
  - `/media/batch` : 3/min
  - `/pdf/status` : 60/min
  - `/speedtest/status` : 60/min
  - Default global : 200/min et 2000/h (filet de sécurité)
  - `/health` exempté (Docker healthcheck)
  - Storage **Redis partagé entre workers gunicorn** en prod (`RATELIMIT_STORAGE_URI`),
    `memory://` en dev. Les erreurs 429 sont renvoyées en JSON sur les routes API.
- **Validation des uploads par magic bytes** (`app/core/uploads.py`, stdlib only,
  sans `python-magic`) : cohérence extension/contenu vérifiée pour jpg/jpeg/png/gif/
  webp/mp4/mov/webm/mkv/avi, batch plafonné à **20 fichiers** et **200 MB cumulés**,
  `Image.MAX_IMAGE_PIXELS = 50 000 000` sur Pillow (anti-bombe d'image).
- **Whitelist des domaines yt-dlp** : seuls YouTube, Vimeo, Dailymotion et TikTok
  sont acceptés (`_is_allowed_url` dans `downloader/routes.py`). Toute
  autre URL est rejetée en 400 avant tout appel yt-dlp. Les schemes `file://`,
  `ftp://`, `javascript:` et `data:` sont explicitement bloqués. L'URL utilisateur
  n'apparaît plus en clair dans les logs : un hash SHA-256 tronqué est utilisé.
- **Timeout FFmpeg** abaissé de **600s → 180s** (limite l'exposition en cas
  d'input malveillant qui ferait hang le décodeur).

### Build

- **Tailwind en build local** (CLI standalone Go, zéro Node) : le Play CDN
  `cdn.tailwindcss.com` est **explicitement déconseillé en production** par
  l'équipe Tailwind. Remplacement par :
  - `tailwind.config.js` extrayant la config inline (darkMode, couleurs primary/dark,
    animations gradient/float/pulse-slow)
  - `app/static/css/input.css` comme point d'entrée
  - Stage dédié `css-builder` dans le `Dockerfile` (debian slim + binaire v3.4.13)
  - Cibles `make tailwind-install` / `tailwind-build` / `tailwind-watch` pour le dev
  - Sortie CSS minifiée, purgée (~10-30 KB vs ~3 MB non compressé du CDN)
- **Font Awesome rapatrié en local** (`app/static/vendor/fontawesome/`, v6.0.0,
  ~900 KB CSS + webfonts). Plus aucune dépendance sur cdnjs.cloudflare.com.
- **SRI obligatoire sur tout CDN restant** : le modèle `Tool` porte désormais un
  type `ExternalScript(src, integrity, crossorigin, referrerpolicy)` — impossible
  d'ajouter un script externe sans hash SHA-384. Appliqué à `qrcode-generator`
  (seul CDN encore référencé).

### Ajouté

- **`app/core/security_headers.py`** : nonce CSP + headers HTTP.
- **`app/core/rate_limit.py`** : instance `Limiter` centralisée.
- **`app/core/uploads.py`** : `validate_upload`, `validate_batch`,
  `configure_pillow_limits`, constantes `MAX_BATCH_FILES` / `MAX_BATCH_BYTES` /
  `MAX_UPLOAD_BYTES`.
- **Service `redis`** dans `compose.yml` : Redis 7.4-alpine, 64 MB cap, politique
  `allkeys-lru`, pas de persistance disque (compteurs rate limit éphémères par
  design), healthcheck, aucun port exposé à l'hôte.
- **Service `librespeed`** dans `compose.yml` : instance LibreSpeed stateless,
  exposée par défaut sur `8081`, intégrée en iframe via `/speedtest/`.
- **Blueprint `speedtest`** : routes `/speedtest/`, `/speedtest/status` et
  redirection `/speedtest`, fallback de configuration si LibreSpeed n'est pas
  disponible.
- **Variables LibreSpeed** : `LIBRESPEED_URL`, `LIBRESPEED_PUBLIC_URL` et
  `LIBRESPEED_PORT` documentées dans `env.example` et le README.
- **Template `errors/429.html`** dédié.
- **37 tests de sécurité** (CSP nonce unique par requête, magic bytes jpg/png
  forgés, rejet d'extensions, plafond batch, whitelist yt-dlp positive + négative,
  rate limit déclenchant 429 au 21e appel, JSON sur erreurs API, `/health` exempté).
- **Test de compat ascendante** : un test smoke vérifie que `/youtube/`
  redirige bien sur `/downloader/`.

### Modifié

- `app/services/main.py` : initialise `limiter`, `configure_pillow_limits(50M)`,
  `register_security_headers(app)`. Le handler d'erreurs HTTP renvoie du JSON
  sur les routes API (`/downloader/*`, `/media/*`, `/pdf/status`, `/essentials/api`)
  même quand le client n'envoie pas `Accept: application/json`.
- `app/services/media_converter/routes.py` : `validate_upload` / `validate_batch`
  en amont, `allowed_file` supprimée (redondante), `quality` plafonné entre 0 et
  100, rejet explicite de `DecompressionBombError`, format de sortie validé.
- `env.example` : nettoyé des 20+ variables fantômes jamais lues par le code.
  Ne liste que ce que l'app consomme réellement.
- `README.md` : documentation mise à jour pour LibreSpeed et la version `1.3.1`.

### Retiré

- **Tailwind Play CDN** (`https://cdn.tailwindcss.com`) — déconseillé en prod.
- **Font Awesome sur cdnjs.cloudflare.com** — remplacé par copie locale.

### Refonte du module Essentials

#### Refondu
- **Module Essentials (refonte complète)** : architecture repensée en **sous-blueprints Flask auto-enregistrés** via une registry (`app/services/essentials/_base.py`). Chaque outil = 1 module Python ~20 lignes + 1 template HTML héritant d'un **layout commun** (`_tool_layout.html`) + 1 fichier JS dédié. Plus besoin de modifier 3 endroits pour ajouter un outil.
- **Migration 100% client-side** : tous les outils historiques tournent désormais dans le navigateur (zéro aller-retour serveur) :
  - Hash via `crypto.subtle.digest` (SHA-1, SHA-256, SHA-384, SHA-512) — **MD5 retiré** car obsolète cryptographiquement
  - Password via `crypto.getRandomValues` + nouveau mode **passphrase** (style Diceware, 4-10 mots)
  - Base64, JSON, Timestamp, Palette de couleurs : JS natif uniquement
  - QR Code : lib `qrcode-generator` en CDN, export PNG **et** SVG
- **Layout unifié** : nouvelle page type `tool-page` avec input à gauche, résultat à droite, feedback **instantané** (debounce 200ms sur les `input` events — plus de boutons « Soumettre »), boutons "Copier" standardisés via `data-copy-target`, notifications toast (`window.ToolUtils`).

#### Ajouté (Essentials)
- **6 nouveaux outils essentiels** (tous client-side) :
  - **UUID generator** — v4 (aléatoire) et v7 (time-ordered, idéal pour clés primaires indexées), options majuscules / sans tirets, génération en batch
  - **JWT decoder** — inspection header + payload, humanisation des timestamps `exp`/`iat`/`nbf`, détection d'expiration (signature **non** vérifiée, clairement affiché)
  - **Regex tester** — match live avec highlight des correspondances, affichage des groupes capturés, support complet des flags (`gmisu`)
  - **URL encoder / decoder** — `encodeURIComponent` / `decodeURIComponent` avec gestion des erreurs
  - **Lorem Ipsum** — mots, phrases ou paragraphes, option « commencer par Lorem ipsum »
  - **Diff viewer** — comparaison ligne par ligne via LCS, highlight +/−, option ignorer les espaces
- **Helpers JS partagés** (`app/static/js/essentials/_common.js`) : `debounce`, `copyToClipboard`, `downloadBlob`, `downloadText`, `notify`, `wireInstantTool`, `bytesToHex`, `base64Encode/Decode` (UTF-8 safe), `base64UrlDecode`.
- **Registry pattern** : la homepage `/essentials/` et le menu nav (desktop + mobile) se génèrent automatiquement depuis `TOOLS` — plus de listes hardcodées.
- **Tests paramétrés** (`tests/test_essentials_tools.py`) : 20+ tests couvrant chaque outil (chargement page, présence du script JS, icône rendue) + vérification que les anciennes routes API renvoient bien 404.

#### Modifié (Essentials)
- **Nav dropdown** : propulsée par la registry via context processor (`essentials_tools_nav`) — les 6 outils les plus utilisés apparaissent automatiquement.
- **Homepage essentials** : passe de 9 à 13 cartes, avec description longue depuis la registry.
- **Endpoints Flask** : renommés pour correspondre au pattern des sous-blueprints (`essentials.qr_generator` → `essentials.qr.index`, etc.).
- **CSS** : ajout de styles spécifiques `tool-page`, `tool-page__grid`, `tool-output__row`, `tool-kv`, `tool-badge`, `tool-strength`, `tool-diff`, `tool-regex-match`, `tool-toast` pour le nouveau layout.

#### Supprimé (Essentials)
- **2 outils retirés** :
  - `text_processor` : utilité marginale, 9 KB de code/template pour peu de valeur.
  - `url_validator` : son allowlist hardcodée de 7 domaines (`google.com`, `github.com`, `wikipedia.org`…) le rendait inutile sur une instance publique, et un vrai validateur SSRF-safe nécessiterait un backend dédié hors scope.
- **`app/services/essentials/tools.py`** (753 lignes) : toutes les classes `QRCodeGenerator`, `PasswordGenerator`, `HashCalculator`, `Base64Encoder`, `JSONFormatter`, `TimestampConverter`, `ColorPaletteGenerator`, `URLValidator`, `TextProcessor` → supprimées, logique réimplémentée côté JS.
- **`app/services/essentials/routes.py`** (313 lignes) : toutes les routes `/essentials/api/*` supprimées → réduction de la surface d'attaque (plus de rate limiting, validation de taille, DoS côté serveur pour ces outils).
- **`qrcode==8.2`** retiré de `requirements.txt` — la génération passe désormais par une lib CDN côté navigateur.
- **`URL_VALIDATOR_ALLOWED_DOMAINS` / `URL_VALIDATOR_ALLOWED_DOMAIN_SUFFIXES`** retirés de `config.py` (orphelins après suppression de l'outil).
- **Anciens templates** : `qr_generator.html`, `password_generator.html`, `text_processor.html`, `color_palette.html`, `url_validator.html`, `hash_calculator.html`, `json_formatter.html` (remplacés par des templates ~30-50 lignes héritant du layout commun).
- **`app/core/security.py`** (392 lignes, `SecurityManager` + décorateurs `require_rate_limit` / `validate_request_size` / `validate_file_upload`) : module dead code (jamais importé nulle part). Remplacé par un stack moderne et **réellement branché** sur les routes — voir la section *Sécurité (lot majeur)* ci-dessus (`security_headers.py`, `rate_limit.py`, `uploads.py`). La sanitisation de nom de fichier reste gérée localement par `app/services/common/utils.py` et `app/services/downloader/routes.py`.
- **`python-magic==0.4.27`** et **`filetype==1.2.0`** retirés de `requirements.txt` — importés uniquement par `security.py`, donc orphelins après sa suppression.

---

## [1.3.0] - 2026-04-24

### Ajouté
- **Logo & branding** : deux variantes SVG (`app/static/img/logo.svg` transparent + `logo-filled.svg` avec fond) — utilisées en header, favicon (y.c. `apple-touch-icon` et `mask-icon`), hero de la page d'accueil (avec animation flottante + `prefers-reduced-motion`) et Open Graph / Twitter cards
- **Outils PDF (Stirling PDF) — mode amnésique** : nouveau blueprint `/pdf` qui embarque [Stirling PDF](https://github.com/Stirling-Tools/Stirling-PDF) via iframe, configuré pour une instance **publique sans rétention de données** :
  - `/configs`, `/logs` et `/tmp` montés en **`tmpfs`** (RAM uniquement, effacés à chaque restart du container)
  - Toutes les analytics désactivées : `SYSTEM_ENABLEANALYTICS=false`, `SYSTEM_ENABLEPOSTHOG=false`, `SYSTEM_ENABLESCARF=false`, `SYSTEM_GOOGLEVISIBILITY=false`, `SHOW_SURVEY=false`, `METRICS_ENABLED=false`, `SYSTEM_SHOWUPDATE=false`
  - Fichiers temp nettoyés agressivement : `MAXAGEHOURS=1`, `CLEANUPINTERVALMINUTES=5`, `STARTUPCLEANUP=true`, `CLEANUPSYSTEMTEMP=true`
  - Features à risque SSRF/privacy désactivées : `SYSTEM_ENABLEURLTOPDF=false`, `SYSTEM_ENABLEMOBILESCANNER=false`, `STORAGE_ENABLED=false`, audit enterprise explicitement off
  - `security_opt: no-new-privileges:true`
  - Seul volume persistant : `stirling_tessdata` (modèles OCR Tesseract, données statiques non-utilisateur)
- **Docker Compose** : service `stirling-pdf` (image `stirlingtools/stirling-pdf:latest`) avec limites de ressources et dépendance ordonnée depuis `toolbox`
- **Variables d'env** : `STIRLING_PDF_URL` (URL interne Docker) et `STIRLING_PDF_PUBLIC_URL` (URL navigateur pour iframe)
- **Healthcheck** : endpoint `/health` exposant le statut de `yt_dlp`, `ffmpeg` et `stirling_pdf` (utilisé par le healthcheck Docker)
- **Tests** : suite pytest avec fixtures partagées (`tests/conftest.py`), 27 tests smoke + unitaires (routes, config, outils essentiels, PDF fallback)
- **requirements-dev.txt** : dépendances développement (pytest, pytest-cov, black, flake8, isort)
- **Makefile** : cible `test-cov` pour lancer les tests avec rapport de couverture

### Modifié
- **Factory Flask** (`app/services/main.py`) : logging unifié via `RotatingFileHandler` (5MB × 5 fichiers), `Flask-Compress` initialisé une seule fois dans `create_app`, bannière ASCII imprimée une seule fois (gate via `TOOLBOX_PRINT_BANNER`), `ProxyFix` avec paramètres explicites, `SEND_FILE_MAX_AGE_DEFAULT` pour le cache des statiques
- **Middleware requêtes** : remplacement de `validate_request` par `_request_start`/`_request_end` avec `time.perf_counter()` — filtrage `/static` et `/health` pour éviter le bruit dans les logs
- **Gestion erreurs** : handler HTTPException centralisé dans `main.py` (HTML pour UI, JSON pour API détecté via `X-Requested-With` ou path `/api/`), `exceptions.py` réservé aux exceptions métier `ToolboxBaseException`
- **FFmpeg** : détection unifiée via `Config.get_ffmpeg_path()` (env var `FFMPEG_PATH`, `shutil.which`, chemins Linux/Windows) — suppression du `.exe` hardcodé multi-plateformes
- **YouTube Downloader** : `tempfile.mkdtemp()` + `@after_this_request` pour garantir le nettoyage des fichiers temporaires, User-Agent Chrome plus récent, classification unifiée des erreurs via `_classify_yt_error`
- **Media Converter** : paramètre `quality` (0-100) désormais effectif sur les vidéos — mapping vers CRF FFmpeg (libx264 / libvpx-vp9) via `_quality_to_crf`
- **URL Validator** : listes de domaines autorisés centralisées dans `config.py` comme source unique (récupérées via `current_app.config`)
- **Homepage** : carte « Outils PDF » (violet) avec CTA dynamique (« Ouvrir » ou « Configurer » selon l'état Stirling)
- **Navigation** : lien PDF actif dans header desktop + mobile avec badge « setup » si Stirling non configuré
- **Page PDF** : ton épuré — suppression des copies marketing (« 150+ outils », « sans envoyer vos documents à un tiers », sous-titres explicatifs redondants), toolbar réduite au titre **« Instance Stirling PDF »** + un simple dot d'état (vert/jaune), bouton « Ouvrir dans un nouvel onglet » en icône seule, bloc fallback avec un seul `docker compose up -d`. Section **« Pourquoi utiliser nos outils ? »** incluse en bas comme sur les autres pages (via `tool_features.html`)
- **Footer** : réduit à l'essentiel — une seule ligne `© {year} · v{version}` + icône GitHub, suppression des liens dupliqués (YouTube/Conversion/Essentiels/PDF déjà dans le header) et du tagline « open source, self-hosted »

### Supprimé
- **`docker-compose.yml` / `docker-compose.hub.yml`** : fusionnés en un unique **`compose.yml`** à la racine (nom moderne recommandé par Compose v2) — toggle build local vs image publique via `TOOLBOX_IMAGE`, ports configurables via `TOOLBOX_PORT` / `STIRLING_PORT`
- **Dossier `docker/`** : scripts et docker-compose migrés à la racine
  - `docker/Makefile`, `docker/docker-build.ps1`, `docker/docker-build.sh` supprimés
  - `docker/docker-compose.hub.yml` déplacé à la racine puis fusionné
- **Dossier `bin/`** : plus nécessaire — FFmpeg détecté dynamiquement via `PATH` ou image Docker
- **CSS morte** : classes inutilisées retirées de `app/static/css/style.css` (`.card-hover-effect`, `.animated-gradient-text`, `.floating-icon`, `.pulse-on-hover`, `.glow-effect`, `.skeleton` et leurs `@keyframes`)
- **Handlers 404/500 dupliqués** : consolidés dans `main.py`, retirés de `exceptions.py`

### Corrigé
- **Bannière ASCII imprimée N fois sous Gunicorn** : n'apparaît désormais qu'une seule fois au démarrage
- **`Flask-Compress` sans effet sous Gunicorn** : initialisé correctement dans `create_app`
- **Chemin FFmpeg Windows hardcodé** sur builds Linux : logique désormais cross-platform
- **Validation de requête trop stricte** : ne bloque plus les requêtes légitimes sans User-Agent
- **Quality vidéo ignorée** dans le media converter : désormais appliquée via CRF

---

## [1.2.0] - 2026-04-10

### Ajouté
- **Design system** : nouveau système CSS partagé pour les pages outils (`.tool-panel`, `.tool-btn`, `.tool-input`, `.tool-select`, `.tool-progress`, `.tool-dropzone`, `.tool-hero`)
- **Footer** : année de copyright dynamique et numéro de version (`v{{ app_version }}`) via context processor
- **Démarrage** : bannière ASCII au lancement avec version, mode, URL, Python, FFmpeg, uploads et routes
- **CLI** : `python run.py --version` utilise désormais `__version__` au lieu d'une valeur hardcodée
- **Sécurité** : auto-génération de `SECRET_KEY` à la première configuration (`make setup`, Docker build, ou au démarrage si le placeholder est détecté)
- **YouTube Downloader** : téléchargement parallèle des fragments HLS/DASH (`concurrent_fragment_downloads: 4`)
- **YouTube Downloader** : retries automatiques (3 tentatives sur les requêtes et fragments)
- **YouTube Downloader** : User-Agent Chrome pour éviter les blocages anti-bot
- **YouTube Downloader** : gestion des erreurs YouTube Premium et vidéos nécessitant une connexion
- **YouTube Downloader** : fallback `channel` → `uploader` pour l'affichage du nom de chaîne

### Modifié
- **Header** : refonte complète en flat design — barre unique, navigation centrée en pill, branding allégé avec accent coloré
- **Header** : dropdown « Essentiels » centré sous le bouton avec pont invisible pour le hover
- **Header** : menu mobile simplifié en panneau léger avec sous-menu dépliable
- **Homepage** : refonte visuelle avec hero compact, grille 4 colonnes, CTA colorés et section « Pourquoi »
- **Page Essentiels** : refonte en grille de cartes horizontales cliquables avec icônes colorées et flèche au hover
- **Page YouTube** : refonte avec `.tool-panel`, `.tool-btn`, `.tool-input` — suppression des ombres lourdes et effets scale
- **Page Conversion Média** : refonte avec `.tool-dropzone`, `.tool-panel`, `.tool-select` — zone de dépôt flat, overlay allégé
- **Textes** : correction de tous les accents manquants sur l'ensemble des templates
- **YouTube Downloader** : mise à jour de `yt-dlp` de `2025.06.25` vers `2026.03.17`
- **YouTube Downloader** : format de sélection vidéo migré vers `bestvideo+bestaudio` (streams séparés mergés par FFmpeg)
- **YouTube Downloader** : passage à un seul appel `extract_info(download=True)` avec `requested_downloads[0]['filepath']`
- **YouTube Downloader** : factorisation des options communes dans `_common_ydl_opts()`
- **Dépendances** : mise à jour globale de toutes les dépendances :
  - Flask `3.0.2` → `3.1.3`
  - Werkzeug `3.0.6` → `3.1.8`
  - python-dotenv `1.0.1` → `1.2.2`
  - Flask-WTF `1.2.1` → `1.2.2`
  - Flask-Compress `1.14` → `1.24`
  - Flask-Caching `2.1.0` → `2.3.1`
  - Pillow `10.3.0` → `12.2.0`
  - qrcode `7.4.2` → `8.2`
  - shortuuid `1.0.11` → `1.0.13`
  - cryptography `42.0.2` → `46.0.7`
  - requests `2.32.2` → `2.33.1`
  - python-dateutil `2.8.2` → `2.9.0.post0`
  - humanize `4.9.0` → `4.15.0`
  - gunicorn `23.0.0` → `25.3.0`
  - brotli `1.1.0` → `1.2.0`
  - orjson `3.9.15` → `3.11.8`
  - certifi `≥2024.2.2` → `≥2026.2.25`
  - urllib3 `≥2.2.0` → `≥2.6.3`
  - bleach `6.1.0` → `6.3.0`
  - psutil `5.9.8` → `7.2.2`
  - marshmallow `3.21.1` → `4.3.0`
  - validators `0.22.0` → `0.35.0`

### Corrigé
- **YouTube Downloader** : suppression de l'appel à `ydl._format_selection()` (méthode privée supprimée en 2026.x)
- **YouTube Downloader** : suppression des options `prefer_ffmpeg` et `keepvideo` dépréciées/supprimées dans yt-dlp 2026.x
- **Frontend** : `textContent` assigné au `<span>` enfant plutôt qu'au `<p>` parent pour ne plus écraser les icônes FontAwesome dans les métadonnées vidéo

---

## [1.1.3] - 2024

### Modifié
- Mise à jour mineure de l'application
- `gunicorn` mis à jour de `21.2.0` vers `23.0.0` (sécurité)
- `werkzeug` mis à jour de `3.0.1` vers `3.0.6` (sécurité)
- `pillow` mis à jour de `10.2.0` vers `10.3.0` (sécurité)
- `requests` mis à jour de `2.31.0` vers `2.32.2` (sécurité)

---

## [1.1.2c] - 2024

### Corrigé
- Corrections diverses

---

## [1.1.2b] - 2024

### Corrigé
- Correctifs supplémentaires de la 1.1.2

---

## [1.1.2] - 2024

### Modifié
- Améliorations générales de stabilité

---

## [1.1.1] - 2024

### Corrigé
- Correctifs de la version 1.1

---

## [1.1.0] - 2024

### Ajouté
- Préparation et mise en production de la version 1.1
- Séparation du JavaScript et du HTML dans les templates
- Amélioration du padding et de l'interface

---

## [1.0.0] - 2024

### Ajouté
- Création initiale du projet
- **YouTube Downloader** : téléchargement de vidéos et audio depuis YouTube
- **Convertisseur de médias** : conversion entre formats d'images et vidéos
- **Outils essentiels** : générateur de QR codes, générateur de mots de passe, raccourcisseur d'URL
- Interface responsive desktop et mobile
- Support Docker et Docker Compose
- Pipeline CI/CD GitHub Actions pour publier une image Docker
