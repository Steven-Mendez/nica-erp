.DEFAULT_GOAL := help
.PHONY: help

# Per-concern fragments — order doesn't matter; help discovers targets via the
# `## ` doc-comment convention in any included fragment.
include make/dev.mk
include make/test.mk
include make/deploy.mk

help: ## list targets
	@awk 'BEGIN {FS = ":.*?## "} \
		/^##@ / {printf "\n\033[1m%s\033[0m\n", substr($$0, 5); next} \
		/^[a-zA-Z0-9_-]+:.*?## / {printf "  %-22s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
