# Operations hub for the blog. One-word commands so no step gets skipped.
# Run `make` with no target to list everything.

.DEFAULT_GOAL := help
MANAGE := uv run --env-file .env python manage.py

.PHONY: help install run migrate new promote test fmt lint lint-content audit check clean

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
