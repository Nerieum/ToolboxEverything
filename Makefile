# =====================================
# Toolbox Everything - Makefile
# =====================================

# Variables
PYTHON := python
PIP := pip
FLASK_APP := run.py
PORT := 8000
VERSION := $(shell if [ -f VERSION ]; then tr -d '\r\n' < VERSION; else echo "0.0.0"; fi)
GHCR_IMAGE ?= ghcr.io/doalou/toolbox_everything
TAILWIND_VERSION := 4.3.3
TAILWIND := $(PYTHON) scripts/tailwind.py

# Couleurs pour l'affichage
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

.PHONY: help setup install dev run build clean test test-cov lint format security check \
        docker-build docker-run tailwind-install tailwind-build tailwind-watch \
        deps-check deps-update freeze

# Affichage de l'aide
help:
	@echo "$(GREEN)Toolbox Everything - Commandes disponibles:$(NC)"
	@echo ""
	@echo "  $(YELLOW)setup$(NC)         - Installation complète (dépendances + configuration)"
	@echo "  $(YELLOW)install$(NC)       - Installation des dépendances"
	@echo "  $(YELLOW)dev$(NC)           - Lancement en mode développement"
	@echo "  $(YELLOW)run$(NC)           - Lancement en mode production"
	@echo "  $(YELLOW)build$(NC)         - Construction de l'application"
	@echo "  $(YELLOW)clean$(NC)         - Nettoyage des fichiers temporaires"
	@echo "  $(YELLOW)test$(NC)          - Exécution des tests"
	@echo "  $(YELLOW)lint$(NC)          - Vérification du code (ruff)"
	@echo "  $(YELLOW)format$(NC)        - Formatage du code (ruff + black)"
	@echo "  $(YELLOW)security$(NC)      - Vérification de sécurité (bandit)"
	@echo "  $(YELLOW)check$(NC)         - Vérifications complètes (lint + security)"
	@echo "  $(YELLOW)docker-build$(NC)  - Construction de l'image Docker"
	@echo "  $(YELLOW)docker-run$(NC)    - Lancement du conteneur Docker"
	@echo ""
	@echo "  $(YELLOW)tailwind-install$(NC) - Télécharge le binaire Tailwind CLI standalone"
	@echo "  $(YELLOW)tailwind-build$(NC)   - Build CSS (minifié) — à lancer avant dev"
	@echo "  $(YELLOW)tailwind-watch$(NC)   - Build CSS en continu (dev)"
	@echo ""

# Installation complète
setup: install
	@echo "$(GREEN)✓ Configuration de l'environnement...$(NC)"
	@mkdir -p logs uploads downloads
	@if [ ! -f .env ]; then \
		cp env.example .env; \
		SECRET=$$($(PYTHON) -c "import secrets; print(secrets.token_hex(32))"); \
		sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$$SECRET/" .env; \
		echo "$(GREEN)✓ Fichier .env créé avec une SECRET_KEY sécurisée$(NC)"; \
	else \
		echo "$(YELLOW)ℹ Fichier .env déjà existant — SECRET_KEY inchangée$(NC)"; \
	fi
	@echo "$(GREEN)✓ Installation terminée !$(NC)"

# Installation des dépendances
install:
	@echo "$(YELLOW)Installation des dépendances...$(NC)"
	$(PIP) install -r requirements.txt
	@echo "$(GREEN)✓ Dépendances installées$(NC)"

# Mode développement (rebuild Tailwind pour éviter un CSS local obsolète)
dev: tailwind-build
	@echo "$(YELLOW)Lancement en mode développement...$(NC)"
	@echo "$(GREEN)Serveur accessible sur http://localhost:$(PORT)$(NC)"
	$(PYTHON) $(FLASK_APP) --dev --port $(PORT)

# Mode production
run:
	@echo "$(YELLOW)Lancement en mode production...$(NC)"
	@echo "$(GREEN)Serveur accessible sur http://localhost:$(PORT)$(NC)"
	$(PYTHON) $(FLASK_APP) --port $(PORT)

# Construction
build: clean install tailwind-build
	@echo "$(GREEN)✓ Application construite$(NC)"

# ──────────────────────────────────────────────────────
# Tailwind CSS (CLI standalone, zéro Node)
# ──────────────────────────────────────────────────────
tailwind-install:
	$(TAILWIND) install

tailwind-build:
	$(TAILWIND) build
	@echo "$(GREEN)✓ CSS généré → app/static/css/tailwind.css$(NC)"

tailwind-watch:
	$(TAILWIND) watch

# Nettoyage
clean:
	@echo "$(YELLOW)Nettoyage des fichiers temporaires...$(NC)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .pytest_cache/ .coverage htmlcov/
	rm -rf uploads/temp/* downloads/temp/* logs/*.log
	@echo "$(GREEN)✓ Nettoyage terminé$(NC)"

# Tests
test:
	@echo "$(YELLOW)Exécution des tests...$(NC)"
	@if [ -d "tests" ]; then \
		$(PYTHON) -m pytest tests/ -v; \
	else \
		echo "$(RED)Aucun dossier de tests trouvé$(NC)"; \
	fi

# Tests avec couverture
test-cov:
	@echo "$(YELLOW)Exécution des tests avec couverture...$(NC)"
	$(PYTHON) -m pytest tests/ -v --cov=app --cov-report=term-missing

# Vérification du code (ruff — config dans pyproject.toml)
lint:
	@echo "$(YELLOW)Vérification du code avec ruff...$(NC)"
	@if command -v ruff >/dev/null 2>&1; then \
		ruff check .; \
		echo "$(GREEN)✓ Code vérifié$(NC)"; \
	else \
		echo "$(RED)ruff non installé. Installation: pip install ruff$(NC)"; \
	fi

# Formatage du code (ruff pour les imports + black — config dans pyproject.toml)
format:
	@echo "$(YELLOW)Formatage du code (ruff + black)...$(NC)"
	@if command -v ruff >/dev/null 2>&1 && command -v black >/dev/null 2>&1; then \
		ruff check --fix .; \
		black .; \
		echo "$(GREEN)✓ Code formaté$(NC)"; \
	else \
		echo "$(RED)ruff/black non installés. Installation: pip install -r requirements-dev.txt$(NC)"; \
	fi

# Vérification de sécurité
security:
	@echo "$(YELLOW)Vérification de sécurité avec bandit...$(NC)"
	@if command -v bandit >/dev/null 2>&1; then \
		bandit -r app/ -f json -o security-report.json || true; \
		bandit -r app/ --exclude=*/tests/*; \
		echo "$(GREEN)✓ Vérification de sécurité terminée$(NC)"; \
	else \
		echo "$(RED)bandit non installé. Installation: pip install bandit$(NC)"; \
	fi

# Vérifications complètes
check: lint security
	@echo "$(GREEN)✓ Toutes les vérifications sont terminées$(NC)"

# Construction Docker
docker-build:
	@echo "$(YELLOW)Construction de l'image Docker (v$(VERSION))...$(NC)"
	docker build -t toolbox-everything:$(VERSION) -t toolbox-everything:latest -t $(GHCR_IMAGE):$(VERSION) -t $(GHCR_IMAGE):latest .
	@echo "$(GREEN)✓ Image Docker construite (v$(VERSION))$(NC)"

# Lancement Docker
docker-run:
	@echo "$(YELLOW)Lancement du conteneur Docker...$(NC)"
	@echo "$(GREEN)Serveur accessible sur http://localhost:$(PORT)$(NC)"
	docker run -p $(PORT):8000 --rm -it toolbox-everything:latest

# Vérification des dépendances
deps-check:
	@echo "$(YELLOW)Vérification des dépendances...$(NC)"
	@if command -v pip-audit >/dev/null 2>&1; then \
		pip-audit; \
	else \
		echo "$(RED)pip-audit non installé. Installation: pip install pip-audit$(NC)"; \
	fi

# Mise à jour des dépendances
deps-update:
	@echo "$(YELLOW)Mise à jour des dépendances...$(NC)"
	$(PIP) install --upgrade -r requirements.txt
	@echo "$(GREEN)✓ Dépendances mises à jour$(NC)"

# Génération du fichier requirements.txt
freeze:
	@echo "$(YELLOW)Génération du fichier requirements.txt...$(NC)"
	$(PIP) freeze > requirements-freeze.txt
	@echo "$(GREEN)✓ Fichier requirements-freeze.txt généré$(NC)" 
