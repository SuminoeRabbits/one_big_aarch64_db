# Makefile for One Big AArch64 Database Project
# Integrates Python database generation and C++ tool building

SHELL := /bin/bash
VENV_DIR := venv39
PYTHON := $(VENV_DIR)/bin/python3
PIP := $(VENV_DIR)/bin/pip
CPP_SOURCE_DIR := cpp_source
BUILD_DIR := $(CPP_SOURCE_DIR)/build

# Database files
SYSREG_DB := aarch64_sysreg_db.duckdb
ISA_DB := aarch64_isa_db.duckdb
SYSREG_XLSX := aarch64_sysreg_db.xlsx
ISA_XLSX := aarch64_isa_db.xlsx

# RAG-optimized JSONL files
SYSREG_JSON := aarch64_sysreg_onebig.jsonl
ISA_JSON := aarch64_isa_onebig.jsonl

# Executables
QUERY_REGISTER := query_register
QUERY_ISA := query_isa

# Python scripts
GEN_SYSREG := gen_aarch64_sysreg_db.py
GEN_ISA := gen_aarch64_isa_db.py
GEN_SYSREG_JSON := gen_aarch64_sysreg_onebig.py
GEN_ISA_JSON := gen_aarch64_isa_onebig.py

# Number of parallel jobs (default to number of CPU cores)
NPROC := $(shell nproc 2>/dev/null || echo 4)

# Enable parallel execution by default (GNU Make 4.0+)
# This allows database generation to run in parallel
MAKEFLAGS += --output-sync=target

.PHONY: all clean setup db build install help test json

# Default target
all: db json build install

# Help message
help:
	@echo "One Big AArch64 Database - Build System"
	@echo ""
	@echo "Usage:"
	@echo "  make setup     - Set up Python virtual environment (first time only)"
	@echo "  make db        - Generate DuckDB databases from XML sources"
	@echo "  make json      - Generate RAG-optimized JSONL files from databases"
	@echo "  make build     - Build C++ query tools"
	@echo "  make install   - Install executables to project root"
	@echo "  make all       - Run db + json + build + install (default)"
	@echo "  make test      - Run tests"
	@echo "  make clean     - Remove generated files and build artifacts"
	@echo "  make clean-all - Remove everything including virtual environment"
	@echo ""
	@echo "Parallel Build:"
	@echo "  make -j        - Use all CPU cores for parallel build"
	@echo "  make -j4       - Use 4 parallel jobs"
	@echo "  make -j\$$(nproc) - Explicitly use all available cores"
	@echo ""
	@echo "Note: Parallel execution is enabled by default for database generation."
	@echo "      C++ compilation uses -j$(NPROC) automatically."
	@echo ""

# Python virtual environment setup
setup:
	@echo "==== Setting up Python virtual environment ===="
	python3 -m venv $(VENV_DIR)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "==== Setup complete ===="

# Generate DuckDB databases
db: $(SYSREG_DB) $(ISA_DB)

$(SYSREG_DB): $(GEN_SYSREG)
	@echo "==== Generating System Register Database ===="
	$(PYTHON) $(GEN_SYSREG)

$(ISA_DB): $(GEN_ISA)
	@echo "==== Generating ISA Database ===="
	$(PYTHON) $(GEN_ISA)

# Generate RAG-optimized JSONL files
json: $(SYSREG_JSON) $(ISA_JSON)

$(SYSREG_JSON): $(SYSREG_DB) $(GEN_SYSREG_JSON)
	@echo "==== Generating System Register OneBig JSONL ===="
	$(PYTHON) $(GEN_SYSREG_JSON)

$(ISA_JSON): $(ISA_DB) $(GEN_ISA_JSON)
	@echo "==== Generating ISA OneBig JSONL ===="
	$(PYTHON) $(GEN_ISA_JSON)

# Build C++ tools
build: $(BUILD_DIR)/Makefile
	@echo "==== Building C++ query tools ===="
	$(MAKE) -C $(BUILD_DIR) -j$(NPROC)

$(BUILD_DIR)/Makefile: $(CPP_SOURCE_DIR)/CMakeLists.txt $(SYSREG_DB) $(ISA_DB)
	@echo "==== Configuring CMake ===="
	mkdir -p $(BUILD_DIR)
	cd $(BUILD_DIR) && cmake ..

# Install executables to project root
install: build
	@echo "==== Installing executables ===="
	$(MAKE) -C $(BUILD_DIR) install
	@echo ""
	@echo "==== Build Complete ===="
	@echo "  Executables installed:"
	@echo "    - $(QUERY_REGISTER)"
	@echo "    - $(QUERY_ISA)"
	@echo ""

# Run tests
test: install
	@echo "==== Running tests ===="
	$(MAKE) -C $(BUILD_DIR) test

# Clean generated files
clean:
	@echo "==== Cleaning generated files ===="
	rm -f $(SYSREG_DB) $(ISA_DB)
	rm -f $(SYSREG_XLSX) $(ISA_XLSX)
	rm -f $(SYSREG_JSON) $(ISA_JSON)
	rm -f $(QUERY_REGISTER) $(QUERY_ISA)
	rm -rf $(BUILD_DIR)
	rm -f $(CPP_SOURCE_DIR)/encoding_data*.cpp $(CPP_SOURCE_DIR)/encoding_data.h
	rm -f $(CPP_SOURCE_DIR)/register_data*.cpp $(CPP_SOURCE_DIR)/register_data.h
	@echo "==== Clean complete ===="

# Clean everything including virtual environment
clean-all: clean
	@echo "==== Removing virtual environment ===="
	rm -rf $(VENV_DIR)
	@echo "==== Clean-all complete ===="
