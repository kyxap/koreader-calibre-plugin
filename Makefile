# Read the version from the .version file
version := $(shell head -n 1 .version 2>/dev/null || echo 0.0.1)

# Dev version components
DATE := $(shell date -u +%Y%m%d)
SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo local)
DEV_VERSION := $(DATE)-$(SHA)-dev
DEV_TUPLE := (0, 0, 0)

# Check for a dev version file in dist, otherwise use the release version
ifeq ($(wildcard dist/.version-dev),)
    effective_version := $(version)
else
    effective_version := $(shell head -n 1 dist/.version-dev)
endif

zip_file = KOReader_Sync_v$(effective_version).zip
zip_contents = about.txt LICENSE plugin-import-name-koreader.txt *.py *.md images/
plugin_index_file_to_upd = pluginIndexKOReaderSync.txt
init_file_to_upd = __init__.py
dist_dir = dist

# Convert the version to tuple format (only take numeric parts for the tuple)
version_tuple := $(shell echo $(version) | sed 's/-.*//' | awk -F. '{print "("$$1", "$$2", "$$3")"}')

# Flatpak support: set FLATPAK=1 to use Flatpak commands
# e.g., make release FLATPAK=1
ifdef FLATPAK
    ifneq ($(shell uname -s 2>/dev/null),Linux)
        $(error FLATPAK=1 is only supported on Linux. For other platforms, please install Calibre natively and run make without FLATPAK=1)
    endif
    ifeq ($(shell command -v flatpak 2>/dev/null),)
        $(error The 'flatpak' command was not found. Please install flatpak or run make without FLATPAK=1)
    endif
    ifeq ($(shell flatpak info com.calibre_ebook.calibre >/dev/null 2>&1; echo $$?),1)
        $(error Calibre Flatpak (com.calibre_ebook.calibre) is not installed. Please install it or run make without FLATPAK=1)
    endif
    CALIBRE_CUSTOMIZE = flatpak run --command=calibre-customize com.calibre_ebook.calibre
    CALIBRE_DEBUG = flatpak run --command=calibre-debug com.calibre_ebook.calibre
else
    CALIBRE_CUSTOMIZE = calibre-customize
    CALIBRE_DEBUG = calibre-debug
endif

# Main targets
# Always clean dev metadata before a formal release
build: clean_dev
	@$(MAKE) update_version
	@$(MAKE) zip

release: lint test build
	@if [ "$$(git rev-parse --abbrev-ref HEAD)" != "main" ]; then \
		echo "Error: You must be on the 'main' branch to release."; \
		exit 1; \
	fi
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Error: Working directory is not clean. Commit all changes before releasing."; \
		exit 1; \
	fi
	@git fetch origin
	@if [ "$$(git rev-parse HEAD)" != "$$(git rev-parse origin/main)" ]; then \
		echo "Error: Your local main is not in sync with origin/main. Push your changes first."; \
		exit 1; \
	fi
	@$(MAKE) tag

# Preparation for a release: creates a branch, updates versions, and commits.
# Allows .version to be dirty so you can edit it before running.
prep-release:
	@if [ -n "$$(git status --short | grep -v ' .version$$')" ]; then \
		echo "Working directory has uncommitted changes (other than .version). Please commit or stash them first."; \
		exit 1; \
	fi
	@echo "Preparing release for version $(version)"
	@git checkout -b "release-prep-$(version)"
	@$(MAKE) update_version
	@$(MAKE) lint
	@$(MAKE) test
	@git add .version $(init_file_to_upd) $(plugin_index_file_to_upd)
	@git commit -m "chore: Prepare release $(version)"
	@echo "Release preparation branch 'release-prep-$(version)' created."
	@echo "Review the changes and then merge to main. Finally, run 'make release' on main."

# Quality tools
test:
	@echo "Running tests..."
	@if [ -d "tests" ]; then \
		pytest tests/; \
	else \
		echo "No tests directory found."; \
		exit 1; \
	fi

lint:
	@echo "Running linting (pylint)..."
	@pylint __init__.py action.py config.py --rcfile=.pylintrc --fail-on=E,F --output-format=colorized --msg-template="{path}:{line}: [{category}] {msg} ({symbol})" || \
	(echo -e "\n\033[0;31m[!!!] CRITICAL ERRORS FOUND - FIX THESE FIRST:\033[0m" && \
	 pylint __init__.py action.py config.py --rcfile=.pylintrc --errors-only && \
	 exit 1)

# Helper targets to bump version in .version file
bump-patch:
	@awk -F. '{print $$1"."$$2"."$$3+1}' .version > .version.tmp && mv .version.tmp .version
	@echo "Version bumped to $$(cat .version)"

bump-minor:
	@awk -F. '{print $$1"."$$2+1".0"}' .version > .version.tmp && mv .version.tmp .version
	@echo "Version bumped to $$(cat .version)"

bump-major:
	@awk -F. '{print $$1+1".0.0"}' .version > .version.tmp && mv .version.tmp .version
	@echo "Version bumped to $$(cat .version)"

pre:
	@if grep "-pre" .version > /dev/null 2>&1; then \
		echo "Version already has -pre suffix"; \
	else \
		sed -i 's/$$/-pre/' .version; \
		echo "Version updated to $$(cat .version)"; \
	fi

zip: $(dist_dir)
	@echo "Creating new $(dist_dir)/$(zip_file)"
	@mkdir -p "$(dist_dir)" && zip -r "$(dist_dir)/$(zip_file)" $(zip_contents)

# Loads current src content, use this if doing dev changes
dev: dev_version
	@$(MAKE) zip
	@$(MAKE) load

dev_version:
	@mkdir -p "$(dist_dir)"
	@echo "$(DEV_VERSION)" > "$(dist_dir)/.version-dev"
	@sed -i 's/^\([[:space:]]*\)version = ([0-9, ]*)/\1version = $(DEV_TUPLE)/' $(init_file_to_upd)
	@if grep -q "^[[:space:]]*version_string =" $(init_file_to_upd); then \
		sed -i "s/^\([[:space:]]*\)version_string = .*/\1version_string = '$(DEV_VERSION)'/" $(init_file_to_upd); \
	else \
		sed -i "/^[[:space:]]*version = /a \    version_string = '$(DEV_VERSION)'" $(init_file_to_upd); \
	fi
	@sed -i 's/Version: [^;]*;/Version: $(DEV_VERSION);/' $(plugin_index_file_to_upd)
	@echo "Dev version set to $(DEV_VERSION)"

# Install the plugin into Calibre
install: zip
	@$(CALIBRE_CUSTOMIZE) -a "$(dist_dir)/$(zip_file)"

# Install and then launch Calibre in debug mode
load: install
	@$(CALIBRE_DEBUG) -g

update_version: update_version_plugin_index update_version_init
	@echo "Versions updated in all files."

update_version_plugin_index:
	@echo "Updating version in $(plugin_index_file_to_upd) to $(version)"
	@sed -i 's/Version: [^;]*;/Version: $(version);/' $(plugin_index_file_to_upd)
	@echo "Version updated in $(plugin_index_file_to_upd)"

update_version_init:
	@echo "Updating version in $(init_file_to_upd) to $(version_tuple)"
	@sed -i 's/^[[:space:]]*version = .*/    version = $(version_tuple)/' $(init_file_to_upd)
	@sed -i "s/^[[:space:]]*version_string = .*/    version_string = \"$(version)\"/" $(init_file_to_upd)
	@echo "Version updated in $(init_file_to_upd)"

clean_dev:
	@rm -f "$(dist_dir)/.version-dev"
	@echo "Dev version metadata removed from $(dist_dir)."

clean: clean_dev
	@rm -rf "$(dist_dir)"
	@echo "Cleaned $(dist_dir) directory"

$(dist_dir):
	@mkdir -p $(dist_dir)
	@echo "Created $(dist_dir) directory"

debug_version:
	@echo "Read version: $(version)"
	@echo "Effective version: $(effective_version)"
	@echo "Version tuple: $(version_tuple)"
	@echo "Zip file: $(zip_file)"

tag:
	@echo "Tagging version v$(version) and pushing to the repository"
	@if git rev-parse "v$(version)" >/dev/null 2>&1; then \
		echo "Tag v$(version) already exists."; \
	else \
		git tag -a "v$(version)" -m "Version $(version)"; \
		git push origin "v$(version)"; \
	fi

md_to_bb:
	@echo "Converting input.md to output.forumbb"
	@python .scripts/md-to-bb.py .scripts/input.md .scripts/output.forumbb
	@echo "Done:"
	@cat .scripts/output.forumbb

.PHONY: build release zip dev install load update_version update_version_plugin_index update_version_init debug_version tag md_to_bb dev_version clean_dev clean prep-release test lint bump-patch bump-minor bump-major

