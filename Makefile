# Walrio Build System Makefile
# Copyright (c) 2025 TAPS OSS
# Project: https://github.com/TAPSOSS/Walrio
# Licensed under the BSD-3-Clause License (see LICENSE file for details)
# Makefile primarily built for GUIs

MAKEFLAGS = --warn-undefined-variables
# make sort behave sanely
export LC_ALL=C

.PHONY: help build build-main build-lite clean deps-check install-deps test check_style gen_doc

# Default target
help:
	@echo "Walrio Build System"
	@echo "==================="
	@echo ""
	@echo "GUI Build Targets:"
	@echo "  build        - Build both WalrioMain and WalrioLite"
	@echo "  build-main   - Build only WalrioMain"
	@echo "  build-lite   - Build only WalrioLite"
	@echo "  build-debug  - Build in debug mode (onedir)"
	@echo "  clean        - Clean build directories"
	@echo "  deps-check   - Check build dependencies" 
	@echo "  install-deps - Install Python dependencies"
	@echo "  test         - Run basic tests"
	@echo ""
	@echo "Development Targets:"
	@echo "  check_style  - Run style checker on all py files"
	@echo "  gen_doc      - Extract documentation from py files"
	@echo ""
	@echo "Examples:"
	@echo "  make build           # Build both GUIs"
	@echo "  make build-main      # Build only main GUI"
	@echo "  make clean build     # Clean then build"

# GUI Build targets
build:
	python .github/scripts/build_gui.py --gui both --clean

build-main:
	python .github/scripts/build_gui.py --gui main --clean

build-lite:
	python .github/scripts/build_gui.py --gui lite --clean

build-debug:
	python .github/scripts/build_gui.py --gui both --clean --debug

clean:
	python .github/scripts/build_gui.py --clean
	@echo "Build directories cleaned"

deps-check:
	python .github/scripts/build_gui.py --no-deps-check --gui both 2>/dev/null || echo "Dependencies missing"

install-deps:
	pip install -r requirements.txt
	pip install pyinstaller PySide6 mutagen python-vlc

test:
	@echo "Running basic syntax checks..."
	python -m py_compile GUI/walrio_main.py
	python -m py_compile GUI/walrio_lite.py
	@echo "Syntax checks passed"

# Development targets (existing)
check_style:
	python3 .github/scripts/enhanced_style_checker.py modules/*py modules/*/*py

gen_doc:
	cd docs && python generate_api_docs.py