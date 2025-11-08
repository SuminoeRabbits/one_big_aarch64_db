# One Big AArch64 Database

> A comprehensive test coverage tracking system for AArch64 System Registers and Instructions

---

## Preface

### Overview

This project provides a unified database solution for managing AArch64 architecture components. Specifically, it creates two interconnected databases using **DuckDB**:

- **`aarch64_sysreg_db.duckdb`** - System Registers (SysReg) database
- **`aarch64_isa_db.duckdb`** - Instruction Set Architecture (ISA) database

These databases serve as comprehensive reference databases for AArch64 system registers and instructions, providing structured access to ARM specification data.

### Purpose

The primary goals of this project are:

1. **Centralized Reference Database**: Maintain a single source of truth for AArch64 SysReg and ISA specifications
2. **Specification Compliance**: Structure data based on official ARM specifications
3. **Feature Mapping**: Track which features (FEAT_*) are associated with each register and instruction
4. **Easy Querying**: Enable SQL-based queries for analyzing ARM architecture components
5. **Cross-platform Analysis**: Provide structured data for architecture analysis and validation

### Source Specifications

This project references the official ARM architecture specifications provided by ARM Developer:

- **Specification Format**: ASL1 (Architecture Specification Language Level 1)
- **Current Version**: 2025-09 (September 2025)
- **Source**: ARM A-Profile Architecture official XML specifications

**Note on Versioning**: The specification version (currently 2025-09) may be updated when ARM releases newer versions of the architecture specifications. The project is designed to accommodate specification updates and migrations.

### Reference Specifications

The following official ARM specifications are used as reference:

- **System Registers**: [SysReg XML (ASL1)](source_202509/README.md) - Comprehensive system register definitions
- **A64 Instructions**: [ISA_A64 XML (ASL1)](source_202509/README.md) - Complete A64 instruction set definitions
- **Architecture Features**: [AARCHMRS (ASL0)](source_202509/README.md) - Feature attribute tables

For detailed information about the source specifications, see [source_202509/README.md](source_202509/README.md).

### Technology Stack

- **Database Engine**: DuckDB - An in-process SQL OLAP database management system
- **Database Format**: `.duckdb` file format
- **Data Source**: Structured representation of ARM XML specifications
- **Query Language**: SQL with DuckDB extensions
- **Implementation**: Python 3 with xml.etree and duckdb modules

---

## Table of Contents

1. [Preface](#preface)
2. [Getting Started](#getting-started) _(Coming soon)_
3. [Database Schema](#database-schema) _(Coming soon)_
4. [Usage Examples](#usage-examples) _(Coming soon)_
5. [Contributing](#contributing) _(Coming soon)_

---

## Getting Started

### Prerequisites

- Python 3.8 or later
- DuckDB Python module: `pip install duckdb`

### Database Generation

#### Step 1: Download and Extract Source Specifications

Download the ARM A-profile System Register specifications from ARM Developer:

```bash
# Download SysReg XML (2025-09 ASL1)
# See source_202509/README.md for download links

# Extract to source_202509/
tar -xzf SysReg_xml_A_profile-2025-09_ASL1.tar.gz -C source_202509/
```

#### Step 2: Generate the Database

Run the database generator script:

```bash
python gen_aarch64_sysreg_db.py
```

**What the script does:**
1. Scans `source_202509/SysReg_xml_A_profile-2025-09_ASL1/` for `AArch64-*.xml` files only
2. Extracts feature names (FEAT_*) from `<reg_condition>` element only (not from `<fields_condition>`)
3. Creates one database row per (feature, register) pair when multiple features exist
4. Feature extraction rules:
   - If `FEAT_AA64` is the ONLY feature → keep as `FEAT_AA64`
   - If `FEAT_AA64` + other features exist → remove `FEAT_AA64`, keep only other features
   - Always exclude `FEAT_AA32` (AArch32 field-level feature, not register-level)
   - If no `<reg_condition>` exists → mark as `NO_FEATURE`
5. Generates `aarch64_sysreg_db.duckdb` with 684 rows (90 features, 646 registers)

**Expected Output:**
```
================================================================================
AArch64 System Register Database Generator
================================================================================

Found XXX AArch64-*.xml files

Parsing AArch64 XML files and populating database...

  [   1] ACCDATA_EL1          -> FEAT_LS64_ACCDATA
  [   2] ACTLR_EL1            -> NO_FEATURE
  ...
```

### Querying the Database

#### Using DuckDB CLI

```bash
# Open the database
duckdb aarch64_sysreg_db.duckdb

# Count all entries
SELECT COUNT(*) FROM aarch64_sysreg;

# View feature-register pairs
SELECT feature_name, register_name FROM aarch64_sysreg LIMIT 10;

# Find all registers for a specific feature
SELECT register_name FROM aarch64_sysreg
WHERE feature_name = 'FEAT_LS64_ACCDATA';

# Count registers per feature
SELECT feature_name, COUNT(*) as register_count
FROM aarch64_sysreg
GROUP BY feature_name
ORDER BY register_count DESC;

# Find all features required by a specific register
SELECT feature_name FROM aarch64_sysreg
WHERE register_name = 'ACCDATA_EL1';
```

#### Using Python

```python
import duckdb

conn = duckdb.connect('aarch64_sysreg_db.duckdb')

# Query all registers for a feature
result = conn.execute("""
    SELECT feature_name, register_name, long_name
    FROM aarch64_sysreg
    WHERE feature_name LIKE 'FEAT_SVE%'
""").fetchall()

for row in result:
    print(f"{row[0]:25s} {row[1]:20s} {row[2]}")

conn.close()
```

## Database Schema

### Main Table: `aarch64_sysreg`

The primary table structure follows a feature-centric design:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `feature_name` | VARCHAR | ARM Architecture Feature (FEAT_*), Column 1 |
| `register_name` | VARCHAR | System Register short name (e.g., ACCDATA_EL1), Column 2 |
| `xml_filename` | VARCHAR | Source XML filename |
| `long_name` | VARCHAR | Full register name |
| `is_internal` | VARCHAR | Whether register is internal |
| `reg_condition` | VARCHAR | Implementation condition from spec |
| `reg_purpose` | VARCHAR | Register purpose description |
| `reg_groups` | VARCHAR | Register groups (comma-separated) |
| `register_width` | VARCHAR | Register width in bits (32, 64, or both) |
| `field_count` | INTEGER | Number of bitfields in register |
| `access_types` | VARCHAR | Access types (RO, RW, etc., comma-separated) |
| `created_at` | TIMESTAMP | Record creation timestamp |

**Key Design Principles:**
1. **One row per (feature, register) pair**: If a register requires multiple features, it creates multiple rows
2. **Feature extraction from `<reg_condition>` only**: Field-level conditions (`<fields_condition>`) are ignored
3. **FEAT_AA64 special handling**:
   - Kept when it's the only feature (baseline AArch64 register)
   - Removed when other features exist (other features are more specific)
4. **FEAT_AA32 always excluded**: This is an AArch32 compatibility feature found in field conditions, not register-level
5. **NO_FEATURE for edge cases**: Registers without `<reg_condition>` element (e.g., ID_AA64SMFR0_EL1)

**Example:**
```
feature_name          | register_name
----------------------|---------------
FEAT_LS64_ACCDATA    | ACCDATA_EL1
```

### Metadata Table: `metadata`

Stores database metadata:

| Column | Type | Description |
|--------|------|-------------|
| `key` | VARCHAR | Metadata key |
| `value` | VARCHAR | Metadata value |
| `updated_at` | TIMESTAMP | Last update time |

**Current metadata keys:**
- `spec_version`: ARM specification version (2025-09)
- `spec_format`: Specification format (ASL1)
- `architecture`: Target architecture (AArch64)
- `source_directory`: Source XML directory path

## Script Implementation Details

### gen_aarch64_sysreg_db.py

**Core Logic:**

```python
# Feature extraction rules
EXCLUDED_FEATURES_BASE = {'FEAT_AArch64', 'FEAT_AA32'}
FEAT_AA64 = 'FEAT_AA64'

# Extract from <reg_condition> only
reg_condition = element.find('.//reg_condition').text
features = re.findall(r'FEAT_\w+', reg_condition)

# Remove FEAT_AA32, FEAT_AArch64
features = features - EXCLUDED_FEATURES_BASE

# Special handling for FEAT_AA64
if FEAT_AA64 in features:
    if len(features) > 1:
        features.discard(FEAT_AA64)  # Remove if other features exist
    # else: keep FEAT_AA64 as the only feature

# If no features found
if not features:
    features = {'NO_FEATURE'}
```

**Database Schema:**
- Primary key: `(feature_name, register_name)` unique constraint
- Auto-increment ID with DuckDB sequence
- One row per feature-register combination

**Expected Results:**
- Total: 684 rows
- FEAT_AA64: 173 registers (baseline)
- Other FEAT_*: 509 rows
- NO_FEATURE: 2 rows (ID_AA64SMFR0_EL1, ID_AA64ZFR0_EL1)

**File Pattern:** Only `AArch64-*.xml` files are processed (excludes `AArch32-*.xml`, `amu.*.xml`, etc.)

## Usage Examples

### Export Database to Excel

```bash
# Export to Excel format for easy viewing
duckdb aarch64_sysreg_db.duckdb -c "COPY (SELECT * FROM aarch64_sysreg) TO 'aarch64_sysreg_db.xlsx' WITH (FORMAT GDAL, DRIVER 'XLSX')"
```

### Query Examples

```sql
-- Count all feature-register pairs
SELECT COUNT(*) FROM aarch64_sysreg;

-- List all FEAT_AA64 baseline registers
SELECT register_name, long_name FROM aarch64_sysreg
WHERE feature_name = 'FEAT_AA64'
ORDER BY register_name;

-- Count registers per feature
SELECT feature_name, COUNT(*) as register_count
FROM aarch64_sysreg
GROUP BY feature_name
ORDER BY register_count DESC;

-- Find all features required by a specific register
SELECT feature_name FROM aarch64_sysreg
WHERE register_name = 'ACCDATA_EL1';
```

## Contributing

_(To be documented)_

---

<div align="center">

**Project Status**: 🚧 Under Development

</div>