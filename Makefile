.DEFAULT_GOAL := help
MANAGE := uv run --env-file .env python manage.py
SOPS_SECRETS := deploy/secrets/secrets.sops.yaml
TOFU := tofu -chdir=deploy/tofu
# Hetzner Object Storage (Ceph) rejects the AWS SDK v2 default integrity
# checksums on PutObject (400 InvalidArgument); only send them when required.
TOFU_S3_ENV := AWS_REQUEST_CHECKSUM_CALCULATION=when_required AWS_RESPONSE_CHECKSUM_VALIDATION=when_required
DEV_IMAGE := localhost/blog:dev
DEV_DB_VOL := blog-dev-db

.PHONY: help install run migrate new promote snapshot test fmt lint lint-content golden audit check clean stack-build stack stack-dev stack-clean secrets-edit tofu-init tofu-plan tofu-apply

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-9s\033[0m %s\n", $$1, $$2}'

install: ## Sync the virtualenv from the lockfile
	uv sync

run: ## Start the dev server on http://127.0.0.1:8787
	$(MANAGE) runserver 127.0.0.1:8787

migrate: ## Apply database migrations
	$(MANAGE) migrate

new: ## Scaffold a post: make new KIND=til SLUG=my-slug
	uv run python -m blog.cli new $(KIND) $(SLUG)

promote: ## Promote a Zettel note: make promote NOTE=~/zettel/note.md
	uv run python -m blog.cli promote $(NOTE)

snapshot: ## Snapshot newly-published posts to the Wayback Machine
	$(MANAGE) snapshot_posts

test: ## Run the test suite
	uv run pytest

fmt: ## Format and auto-fix lint (mutates files)
	uv run ruff format .
	uv run ruff check --fix .

lint: ## Static type check (ty)
	uv run ty check

audit: ## Scan dependencies for known vulnerabilities
	uv run pip-audit

lint-content: ## Lint the Markdown in content/
	uv run python -m blog.lint_content content

# Regenerate golden files after an intentional renderer/template change, then
# review the rewrite with `git diff tests/golden` before committing.
golden: ## Regenerate golden files (tests/golden); review with git diff
	uv run python -m scripts.golden

check: ## All CI gates, non-mutating — run before you push
	uv run ruff check .
	uv run ruff format --check .
	uv run ty check
	uv run pytest
	uv run python -m blog.lint_content content
	uv run pip-audit

clean: ## Remove caches and build artefacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .ty_cache build dist *.egg-info

# --- Local container smoke test. Reuses deploy/Containerfile (the prod image),
#     so there is no second topology to drift. `make run` stays the daily loop;
#     this is for "does the prod image build, boot, and serve" before deploy. ---

stack-build: ## Build the production image locally (deploy/Containerfile)
	podman build -f deploy/Containerfile -t $(DEV_IMAGE) .

stack: stack-build ## Run the prod image on :8000 (migrate, sync_content, gunicorn)
	@echo "Prod settings force HTTPS, so the browser will be redirected. Hit it with:"
	@echo "  curl -sI -H 'X-Forwarded-Proto: https' -H 'Host: localhost' http://localhost:8000/"
	podman run --rm -it -p 8000:8000 \
		-v $(DEV_DB_VOL):/app/data \
		-e DATABASE_PATH=/app/data/db.sqlite3 \
		-e DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
		-e DJANGO_SECRET_KEY=$$(openssl rand -base64 32) \
		$(DEV_IMAGE) \
		sh -c "uv run --no-sync python manage.py migrate --noinput \
			&& uv run --no-sync python manage.py sync_content \
			&& uv run --no-sync gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2"

stack-dev: stack-build ## Run the prod image with dev settings — browsable on http://127.0.0.1:8000
	@echo "Browsable (no HTTPS redirect): http://127.0.0.1:8000  — use 127.0.0.1, not localhost (HSTS)."
	podman run --rm -it -p 127.0.0.1:8000:8000 \
		-v $(DEV_DB_VOL):/app/data \
		-e DATABASE_PATH=/app/data/db.sqlite3 \
		-e DJANGO_SETTINGS_MODULE=config.settings.dev \
		-e DJANGO_SECRET_KEY=$$(openssl rand -base64 32) \
		$(DEV_IMAGE) \
		sh -c "uv run --no-sync python manage.py migrate --noinput \
			&& uv run --no-sync python manage.py sync_content \
			&& uv run --no-sync gunicorn config.wsgi:application --bind 0.0.0.0:8000 \
				--worker-class gthread --workers 2 --threads 4"

stack-clean: ## Remove the local dev image and its database volume
	-podman volume rm $(DEV_DB_VOL)
	-podman rmi $(DEV_IMAGE)

# --- Infra (sops + OpenTofu). See deploy/secrets/README.md. ---

secrets-edit: ## Edit the encrypted secrets file in $EDITOR (sops)
	sops $(SOPS_SECRETS)

tofu-init: ## tofu init against the S3 backend (checksum-safe). First run: make tofu-init MIGRATE=-migrate-state
	$(TOFU_S3_ENV) $(TOFU) init -backend-config=backend.hcl $(MIGRATE)

tofu-plan: ## tofu plan with secrets injected from sops as TF_VAR_*
	$(TOFU_S3_ENV) sops exec-env $(SOPS_SECRETS) '$(TOFU) plan'

tofu-apply: ## tofu apply with secrets injected from sops as TF_VAR_*
	$(TOFU_S3_ENV) sops exec-env $(SOPS_SECRETS) '$(TOFU) apply'
