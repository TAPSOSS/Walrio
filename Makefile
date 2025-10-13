# Walrio Build System Makefile
# Copyright (c) 2025 TAPS OSS
# Project: https://github.com/TAPSOSS/Walrio
# Licensed under the BSD-3-Clause License (see LICENSE file for details)

MAKEFLAGS = --warn-undefined-variables
export LC_ALL=C

.PHONY: help build build-main build-lite build-debug clean deps-check install-deps test check_style gen_doc bundle-gstreamer

# Default target
help:
	@echo "Walrio Build System"
	@echo "==================="
	@echo ""
	@echo "GUI Build Targets:"
	@echo "  build           - Build both WalrioMain and WalrioLite (PyInstaller, onefile)"
	@echo "  build-main      - Build only WalrioMain"
	@echo "  build-lite      - Build only WalrioLite"
	@echo "  build-debug     - Build both GUIs in debug mode (onedir)"
	@echo "  bundle-gstreamer - Bundle shared GStreamer libraries into dist/"
	@echo "  clean           - Clean build directories and artifacts"
	@echo ""
	@echo "Development Targets:"
	@echo "  deps-check      - Check build dependencies"
	@echo "  install-deps    - Install Python dependencies"
	@echo "  test            - Run basic tests"
	@echo "  check_style     - Run style checker on all py files"
	@echo "  gen_doc         - Extract documentation from py files"
	@echo ""
	@echo "Examples:"
	@echo "  make build"
	@echo "  make build-main"
	@echo "  make clean build"
	@echo "  make bundle-gstreamer"

# GUI Build targets
build: build-main build-lite bundle-gstreamer

build-main:
ifeq ($(OS),Windows_NT)
	venv\Scripts\python.exe -m PyInstaller GUI/walrio_main.spec
else
	pyinstaller GUI/walrio_main.spec
endif

build-lite:
ifeq ($(OS),Windows_NT)
	venv\Scripts\python.exe -m PyInstaller GUI/walrio_lite.spec
else
	pyinstaller GUI/walrio_lite.spec
endif

build-debug:
ifeq ($(OS),Windows_NT)
	venv\Scripts\python.exe -m PyInstaller GUI/walrio_main.spec --onedir --debug
	venv\Scripts\python.exe -m PyInstaller GUI/walrio_lite.spec --onedir --debug
else
	pyinstaller GUI/walrio_main.spec --onedir --debug
	pyinstaller GUI/walrio_lite.spec --onedir --debug
endif

# Bundle essential GStreamer libraries for portability
bundle-gstreamer:
ifeq ($(OS),Windows_NT)
	@echo "Bundling essential GStreamer DLLs into dist/"
	@if exist "C:\msys64\mingw64\bin\libgst*.dll" copy /Y C:\msys64\mingw64\bin\libgst*.dll dist\
else
	@echo "Bundling essential GStreamer libraries into dist/"
	@mkdir -p dist/gstreamer-1.0
	@for dir in /usr/lib64/gstreamer-1.0 /usr/lib/gstreamer-1.0; do \
		if [ -d $$dir ]; then \
			cp -v $$dir/libgst*.so dist/gstreamer-1.0/ 2>/dev/null || true; \
		fi \
	done
	@for dir in /usr/lib64 /usr/lib; do \
		if [ -d $$dir ]; then \
			cp -v $$dir/libgst*.so* dist/ 2>/dev/null || true; \
		fi \
	done
endif

clean:
	rm -rf dist build __pycache__ *.spec GUI/*.spec
	@echo "Build directories and artifacts cleaned"

deps-check:
	@echo "Checking Python dependencies..."
	python -m pip check || echo "Some dependencies may be missing or incompatible."

install-deps:
	pip install -r requirements.txt

test:
	python -m py_compile GUI/walrio_main.py
	python -m py_compile GUI/walrio_lite.py

check_style:
	python3 .github/scripts/enhanced_style_checker.py modules/*py modules/*/*py

gen_doc:
	cd docs && python generate_api_docs.py