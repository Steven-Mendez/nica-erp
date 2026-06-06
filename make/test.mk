.PHONY: test test-e2e-smoke

##@ Tests
# make test                          BE all lanes + FE vitest run (no coverage, no Playwright)
# make test SCOPE=be|fe              restrict to one stack
# make test LANE=unit|integration|e2e  pick a backend lane (FE e2e uses test-e2e-smoke)
# make test COV=1                    add coverage gates (+ FE inventory matrix when no LANE)
test: ## BE pytest + FE vitest. Vars: SCOPE=be|fe LANE=unit|integration|e2e COV=1
	@scope='$(SCOPE)'; lane='$(LANE)'; cov='$(COV)'; \
	if [ "$$scope" != "fe" ]; then \
		case "$$lane" in \
			unit)        be_path='tests/unit' ;; \
			integration) be_path='tests/integration' ;; \
			e2e)         be_path='tests/e2e' ;; \
			'')          be_path='' ;; \
			*) echo "Unknown LANE=$$lane (use unit|integration|e2e)" >&2; exit 2 ;; \
		esac; \
		be_cov=''; \
		if [ "$$cov" = "1" ]; then \
			be_cov='--cov=src/contexts/tenants --cov=src/contexts/identity --cov=src/shared_kernel --cov-report=term-missing --cov-fail-under=89'; \
		fi; \
		( cd apps/api && uv run pytest $$be_path $$be_cov ); \
	fi
	@scope='$(SCOPE)'; lane='$(LANE)'; cov='$(COV)'; \
	if [ "$$scope" != "be" ]; then \
		case "$$lane" in \
			unit)        ( cd apps/web && pnpm test:unit ) ;; \
			integration) ( cd apps/web && pnpm test:integration ) ;; \
			e2e)         echo "Frontend e2e uses Playwright — run: make test-e2e-smoke" >&2 ;; \
			'') \
				if [ "$$cov" = "1" ]; then \
					( cd apps/web && pnpm exec vitest run --coverage && pnpm test:layout && pnpm test:matrix ); \
				else \
					( cd apps/web && pnpm test:run ); \
				fi ;; \
			*) echo "Unknown LANE=$$lane (use unit|integration|e2e)" >&2; exit 2 ;; \
		esac; \
	fi

test-e2e-smoke: ## Playwright @smoke (Chromium) — separate runner, opt-in
	cd apps/web && pnpm test:e2e:smoke
