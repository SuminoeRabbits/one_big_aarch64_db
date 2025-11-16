# One Big AArch64 Database

> A comprehensive reference database for AArch64 System Registers and Instructions

**Release**: 2025.11
**Specification Version**: ARM A-Profile 2025-09 (ASL1)

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
cat << EOF > requirements.txt
duckdb>=0.8.0,<2.0.0
pandas>=1.3.0,<3.0.0
openpyxl>=3.0.9,<4.0.0
EOF
python -m venv myenv && source myenv/bin/activate && pip install --upgrade pip && \
pip install -r requirements.txt
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
feature_name          | register_name  | field_count
----------------------|----------------|-------------
FEAT_LS64_ACCDATA    | ACCDATA_EL1    | 2
FEAT_NMI             | ALLINT         | 3
```

### Field Details Table: `aarch64_sysreg_fields`

This table stores detailed bit-field information for each register. One row per field within a register.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `register_name` | VARCHAR | System Register short name (foreign key to aarch64_sysreg) |
| `field_name` | VARCHAR | Field name (e.g., ALLINT, RES0, ACCDATA) |
| `field_msb` | INTEGER | Most significant bit position (0-127) |
| `field_lsb` | INTEGER | Least significant bit position (0-127) |
| `field_width` | INTEGER | Field width in bits (msb - lsb + 1) |
| `field_position` | VARCHAR | Bit position in [msb:lsb] format |
| `field_description` | VARCHAR | Description of the field's purpose and behavior |
| `created_at` | TIMESTAMP | Record creation timestamp |

**Key Design Principles:**
1. **One row per field**: Each bitfield in a register gets its own row
2. **64-bit mapping**: All fields map to positions within a 64-bit (or 32-bit) register space
3. **MSB ordering**: Fields are naturally ordered by MSB position (descending)
4. **Field descriptions**: Extracted from `<field_description>` elements in ARM XML specifications

**Example:**
```
register_name | field_name | field_msb | field_lsb | field_width | field_position | field_description
--------------|------------|-----------|-----------|-------------|----------------|------------------
ALLINT        | RES0       | 63        | 14        | 50          | [63:14]        | Reserved, RES0.
ALLINT        | ALLINT     | 13        | 13        | 1           | [13:13]        | All interrupt mask...
ALLINT        | RES0       | 12        | 0         | 13          | [12:0]         | Reserved, RES0.
ACCDATA_EL1   | RES0       | 63        | 32        | 32          | [63:32]        | Reserved, RES0.
ACCDATA_EL1   | ACCDATA    | 31        | 0         | 32          | [31:0]         | Accumulation data...
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

### Generate Database with Docker

You can generate the database using Docker without installing Python or DuckDB locally (works on Windows, macOS, and Linux).

**Prerequisites:**
- Download and extract source specifications as described in [Step 1: Download and Extract Source Specifications](#step-1-download-and-extract-source-specifications)
- The source files (`source_202509/`) will be shared with the Docker container via volume mount

```bash
# Pull Python 3 Docker image
docker pull python:3.11-slim

# Run the database generation script inside Docker
# The current directory is mounted to /workspace in the container
docker run --rm -v $(pwd):/workspace -w /workspace python:3.11-slim bash -c "
  pip install --quiet duckdb pandas openpyxl lxml &&
  python gen_aarch64_sysreg_db.py
"

# For Windows PowerShell, use:
docker run --rm -v ${PWD}:/workspace -w /workspace python:3.11-slim bash -c "pip install --quiet duckdb pandas openpyxl lxml && python gen_aarch64_sysreg_db.py"

# For Windows CMD, use:
docker run --rm -v %cd%:/workspace -w /workspace python:3.11-slim bash -c "pip install --quiet duckdb pandas openpyxl lxml && python gen_aarch64_sysreg_db.py"
```

**How it works:**
- `-v $(pwd):/workspace` mounts your current directory (containing `source_202509/`, `gen_aarch64_sysreg_db.py`) to `/workspace` inside the Docker container
- The script reads XML files from the shared `source_202509/` directory
- Generated database files are written back to your host directory

**This will create:**
- `aarch64_sysreg_db.duckdb` - The DuckDB database file
- `aarch64_sysreg_db.xlsx` - Excel export of the database

### Using DuckDB CLI with Docker

If you don't have DuckDB CLI installed locally, you can use Docker to interact with the database:

```bash
# Pull official DuckDB Docker image
docker pull duckdb/duckdb:latest

# Interactive SQL shell
docker run -it --rm -v $(pwd):/data duckdb/duckdb:latest /data/aarch64_sysreg_db.duckdb

# Run a single query
docker run --rm -v $(pwd):/data duckdb/duckdb:latest /data/aarch64_sysreg_db.duckdb \
  -c "SELECT COUNT(*) as total_rows FROM aarch64_sysreg"

# Export to Excel using Docker
docker run --rm -v $(pwd):/data duckdb/duckdb:latest /data/aarch64_sysreg_db.duckdb \
  -c "COPY (SELECT * FROM aarch64_sysreg) TO '/data/aarch64_sysreg_db.xlsx' WITH (FORMAT GDAL, DRIVER 'XLSX')"
```

### Export Database to Excel

```bash
# Run the export script to create Excel file with multiple sheets
python3 export_to_excel.py
```

This creates `aarch64_sysreg_db.xlsx` with 3 sheets:
- **`registers`** - Main register table (684 feature-register mappings)
- **`fields`** - Field details table (7,967 bit-field definitions)
- **`registers_with_fields`** - Joined view for easy analysis

### Query Register Information (Interactive Agent)

Use the query agent to get information about specific registers and bit fields:

```bash
# Query a specific bit position in a register
python3 query_register.py 'HCR_EL2[1]'

# Query a bit range (can span multiple fields)
python3 query_register.py 'HCR_EL2[31:8]'

# Query all information about a register
python3 query_register.py 'ALLINT'

# Query another bit field
python3 query_register.py 'ACCDATA_EL1[31]'
```

**Supported query formats:**
- `REGISTER_NAME[bit]` - Query a single bit position (e.g., `HCR_EL2[1]`)
- `REGISTER_NAME[high:low]` - Query a bit range (e.g., `HCR_EL2[31:8]`)
- `REGISTER_NAME` - Query entire register information (e.g., `ALLINT`)

**Example output for `HCR_EL2[1]`:**
```
================================================================================
Register: HCR_EL2
Bit Position: [1]
================================================================================

Field Name:     SWIO
Field Position: [1:1]
Field Width:    1 bits

Explanation:
  Bit 1 belongs to the 'SWIO' field,
  which spans bits [1:1] (1 bits total).
```

**Example output for `HCR_EL2[31:8]` (bit range query):**
```
================================================================================
Register: HCR_EL2
Bit Range: [31:8] (24 bits)
================================================================================

This range spans 27 field(s):

Bit Position    Field Name                     Width
-------------------------------------------------------
[31:31]         RW                               1 bits
[31:31]         RAO/WI                           1 bits
[30:30]         TRVM                             1 bits
[29:29]         HCD                              1 bits
[29:29]         RES0                             1 bits
...
```

**Example output for `ALLINT`:**
```
================================================================================
Register: ALLINT
================================================================================

Long Name:      All Interrupt Mask Bit
Register Width: 64 bits
Field Count:    3

Purpose:
  Allows access to the all interrupt mask bit.

Bit Field Layout:

Bit Position    Field Name                     Width
-------------------------------------------------------
[63:14]         RES0                            50 bits
[13:13]         ALLINT                           1 bits
[12:0]          RES0                            13 bits
```

### Query Examples

#### Register Queries

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

#### Field Queries

```sql
-- View all fields for a specific register (with descriptions)
SELECT
    field_name,
    field_position,
    field_width,
    field_description
FROM aarch64_sysreg_fields
WHERE register_name = 'ALLINT'
ORDER BY field_msb DESC;

-- Find all registers with a specific field name
SELECT DISTINCT register_name
FROM aarch64_sysreg_fields
WHERE field_name = 'RES0'
ORDER BY register_name;

-- Count fields per register
SELECT
    register_name,
    COUNT(*) as field_count
FROM aarch64_sysreg_fields
GROUP BY register_name
ORDER BY field_count DESC
LIMIT 10;

-- Join registers and fields for complete view (with descriptions)
SELECT
    r.feature_name,
    r.register_name,
    r.long_name,
    f.field_name,
    f.field_position,
    f.field_width,
    f.field_description
FROM aarch64_sysreg r
JOIN aarch64_sysreg_fields f ON r.register_name = f.register_name
WHERE r.register_name = 'ALLINT'
ORDER BY f.field_msb DESC;

-- Find registers with specific bit field at a position
SELECT DISTINCT register_name
FROM aarch64_sysreg_fields
WHERE field_msb >= 13 AND field_lsb <= 13
ORDER BY register_name;

-- Most common field names
SELECT
    field_name,
    COUNT(*) as occurrence_count
FROM aarch64_sysreg_fields
GROUP BY field_name
ORDER BY occurrence_count DESC
LIMIT 20;
```

## Release Information

### Version 2025.11

**Release Date**: November 2025

**What's Included:**
- AArch64 System Register Database (`aarch64_sysreg_db.duckdb`)
- 684 feature-register mappings
- 90 unique ARM architecture features (FEAT_*)
- 646 unique system registers
- Excel export (`aarch64_sysreg_db.xlsx`)
- Database generation script (`gen_aarch64_sysreg_db.py`)

**Specification Source:**
- ARM A-Profile Architecture 2025-09 (ASL1 format)
- SysReg XML specifications

---

<div align="center">

**Release Version**: 2025.11 | **Specification**: ARM 2025-09

</div>
