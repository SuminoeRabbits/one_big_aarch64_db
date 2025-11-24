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
2. [System Register Database](#system-register-database)
3. [ISA Database](#isa-database)

---

## System Register Database

### Getting Started

#### Prerequisites

- Python 3.8 or later
- DuckDB Python module: `pip install duckdb`

#### Database Generation

##### Step 1: Download and Extract Source Specifications

Download the ARM A-profile System Register specifications from ARM Developer:

```bash
# Download SysReg XML (2025-09 ASL1)
# See source_202509/README.md for download links

# Extract to source_202509/
tar -xzf SysReg_xml_A_profile-2025-09_ASL1.tar.gz -C source_202509/
```

##### Step 2: Generate the Database

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
6. Automatically exports the database to `aarch64_sysreg_db.xlsx` (3 sheets: registers, fields, joined view)

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

Exporting to /path/to/aarch64_sysreg_db.xlsx...
  [1/3] Exporting 'registers' sheet...
  [2/3] Exporting 'fields' sheet...
  [3/3] Exporting 'registers_with_fields' sheet (joined view)...
Export completed successfully!
Done!
```

#### Querying the Database

##### Using Query Agent (Recommended)

The `query_register.py` script provides a convenient command-line interface to query registers and fields:

```bash
# Query a specific bit position
python3 query_register.py 'HCR_EL2[1]'

# Query a bit range
python3 query_register.py 'HCR_EL2[31:8]'

# Query by register and field name
python3 query_register.py 'HCR_EL2.TGE'

# Query by register and field name with bit range verification
python3 query_register.py 'TRCIDR12.NUMCONDKEY[31:0]'

# Query entire register information
python3 query_register.py 'ACCDATA_EL1'

# Query field across all registers (finds all registers containing this field)
python3 query_register.py 'NUMCONDKEY'
python3 query_register.py 'AES'
python3 query_register.py 'TGE'

# Query all fields with specific field definition
python3 query_register.py 'RES0'
python3 query_register.py 'RES1'
python3 query_register.py 'UNPREDICTABLE'
```

**Supported Query Formats:**
- `REGISTER_NAME[bit]` - Query specific bit position (e.g., `HCR_EL2[1]`)
- `REGISTER_NAME[high:low]` - Query bit range (e.g., `HCR_EL2[31:8]`)
- `REGISTER_NAME.FIELD` - Query by field name (e.g., `HCR_EL2.TGE`)
- `REGISTER_NAME.FIELD[range]` - Query with field verification (e.g., `TRCIDR12.NUMCONDKEY[31:0]`)
- `REGISTER_NAME` - Query entire register (e.g., `ALLINT`)
- `FIELD_NAME` - Search field across all registers (e.g., `NUMCONDKEY`, `AES`)
- `FIELD_DEFINITION` - Query all fields by definition (e.g., `RES0`, `RES1`, `UNPREDICTABLE`, `UNDEFINED`, `RAO`, `UNKNOWN`)

**Example Outputs:**

```bash
# Single bit query
$ python3 query_register.py 'HCR_EL2[1]'
================================================================================
Register: HCR_EL2
Bit Position: [1]
================================================================================

Long Name:      Hypervisor Configuration Register
Register Width: 64 bits
Features:       FEAT_AA64

Field Name:     SWIO
Field Position: [1:1]
Field Width:    1 bits
Field Definition: RES1

Description:
  Set/Way Invalidation Override. Causes EL1 execution of the data cache
  invalidate by set/way instructions to perform a data cache clean and
  invalidate by set/way...

Explanation:
  Bit 1 belongs to the 'SWIO' field,
  which spans bits [1:1] (1 bits total).
```

```bash
# Field name query across all registers
$ python3 query_register.py 'TGE'
================================================================================
Field Name: TGE
Found in 4 register(s)
================================================================================

[1] Register: HCRMASK_EL2
    Long Name:      Hypervisor Configuration Masking Register
    Register Width: 64 bits
    Features:       FEAT_SRMASK2

    Field Position: [27:27]
    Field Width:    1 bits

    Description:
      Mask bit for TGE.

--------------------------------------------------------------------------------

[2] Register: HCR_EL2
    Long Name:      Hypervisor Configuration Register
    Register Width: 64 bits
    Features:       FEAT_AA64

    Field Position: [27:27]
    Field Width:    1 bits

    Description:
      Trap General Exceptions, from EL0. HCR_EL2.TGE must not be cached in a TLB.

[... more registers ...]
```

```bash
# Field definition query
$ python3 query_register.py 'RES0' | head -10
ACCDATA_EL1.RES0[63:32]
ALLINT.RES0[63:14]
ALLINT.RES0[12:0]
AMCFGR_EL0.RES0[63:32]
AMCFGR_EL0.RES0[27:25]
AMCG1IDR_EL0.RES0[63:16]
AMCNTENCLR0_EL0.RES0[63:16]
AMCNTENCLR1_EL0.RES0[63:16]
AMCNTENSET0_EL0.RES0[63:16]
AMCNTENSET1_EL0.RES0[63:16]
```

##### Using DuckDB CLI

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

##### Using Python

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

### Database Schema

#### Main Table: `aarch64_sysreg`

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

#### Field Details Table: `aarch64_sysreg_fields`

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
| `field_definition` | VARCHAR | Field definition (RES0, RES1, RAO, WI, UNKNOWN, UNDEFINED, UNPREDICTABLE), or NULL if not applicable |
| `created_at` | TIMESTAMP | Record creation timestamp |

**Key Design Principles:**
1. **One row per field**: Each bitfield in a register gets its own row
2. **64-bit mapping**: All fields map to positions within a 64-bit (or 32-bit) register space
3. **MSB ordering**: Fields are naturally ordered by MSB position (descending)
4. **Field descriptions**: Extracted from `<field_description>` elements in ARM XML specifications
5. **Field definitions**: Extracted from field attributes (`rwtype`, `reserved_type`) and `<arm-defined-word>` tags
   - Common values: RES0 (Reserved, must be 0), RES1 (Reserved, must be 1), RAO (Read-As-One), WI (Write Ignored), UNKNOWN, UNDEFINED, UNPREDICTABLE
   - NULL if the field has no special definition (i.e., it's a normal functional field)

**Example:**
```
register_name | field_name | field_msb | field_lsb | field_width | field_position | field_description         | field_definition
--------------|------------|-----------|-----------|-------------|----------------|---------------------------|------------------
ALLINT        | RES0       | 63        | 14        | 50          | [63:14]        | Reserved, RES0.           | RES0
ALLINT        | ALLINT     | 13        | 13        | 1           | [13:13]        | All interrupt mask...     | NULL
ALLINT        | RES0       | 12        | 0         | 13          | [12:0]         | Reserved, RES0.           | RES0
ACCDATA_EL1   | RES0       | 63        | 32        | 32          | [63:32]        | Reserved, RES0.           | RES0
ACCDATA_EL1   | ACCDATA    | 31        | 0         | 32          | [31:0]         | Accumulation data...      | NULL
```

#### Metadata Table: `metadata`

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

### Script Implementation Details

#### gen_aarch64_sysreg_db.py

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

### Usage Examples

#### Generate Database with Docker

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

#### Using DuckDB CLI with Docker

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



#### Query Register Information (Interactive Agent)

Use the query agent to get information about specific registers and bit fields:

```bash
# Query a specific bit position in a register
python3 query_register.py 'HCR_EL2[1]'

# Query a bit range (can span multiple fields)
python3 query_register.py 'HCR_EL2[31:8]'

# Query by register and field name
python3 query_register.py 'HCR_EL2.TGE'

# Query by register and field name with bit range verification
python3 query_register.py 'TRCIDR12.NUMCONDKEY[31:0]'

# Query all information about a register
python3 query_register.py 'ALLINT'

# Query field across all registers
python3 query_register.py 'NUMCONDKEY'
python3 query_register.py 'AES'
python3 query_register.py 'TGE'

# Query all fields with specific field definition
python3 query_register.py 'RES0'
python3 query_register.py 'RES1'
python3 query_register.py 'UNPREDICTABLE'
```

**Supported query formats:**
- `REGISTER_NAME[bit]` - Query a single bit position (e.g., `HCR_EL2[1]`)
- `REGISTER_NAME[high:low]` - Query a bit range (e.g., `HCR_EL2[31:8]`)
- `REGISTER_NAME.FIELD` - Query by field name (e.g., `HCR_EL2.TGE`)
- `REGISTER_NAME.FIELD[range]` - Query with field verification (e.g., `TRCIDR12.NUMCONDKEY[31:0]`)
- `REGISTER_NAME` - Query entire register information (e.g., `ALLINT`)
- `FIELD_NAME` - Search field across all registers (e.g., `NUMCONDKEY`, `AES`, `TGE`)
- `FIELD_DEFINITION` - Query all fields by definition (e.g., `RES0`, `RES1`, `UNPREDICTABLE`, `UNDEFINED`, `RAO`, `UNKNOWN`)

**Example output for `HCR_EL2[1]`:**
```
================================================================================
Register: HCR_EL2
Bit Position: [1]
================================================================================

Long Name:      Hypervisor Configuration Register
Register Width: 64 bits
Features:       FEAT_AA64

Field Name:     SWIO
Field Position: [1:1]
Field Width:    1 bits
Field Definition: NULL

Description:
  Set/Way Invalidation Override. Causes EL1 execution of the data cache
  invalidate by set/way instructions to perform a data cache clean and
  invalidate by set/way...

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

Long Name:      Hypervisor Configuration Register
Register Width: 64 bits
Features:       FEAT_AA64

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

**Example output for `HCR_EL2.TGE` (field name query):**
```
================================================================================
Register: HCR_EL2
Field Name: TGE
================================================================================

Long Name:      Hypervisor Configuration Register
Register Width: 64 bits
Features:       FEAT_AA64

Field Name:     TGE
Field Position: [27:27]
Field Width:    1 bits
Field Definition: NULL

Description:
  Trap General Exceptions, from EL0. HCR_EL2.TGE must not be cached in a TLB.

Explanation:
  The 'TGE' field is located at bits [27:27],
  spanning 1 bits total in the HCR_EL2 register.
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

Bit Position    Field Name                     Width       Definition
------------------------------------------------------------------------
[63:14]         RES0                            50 bits     RES0
[13:13]         ALLINT                           1 bits     NULL
[12:0]          RES0                            13 bits     RES0
```

#### Query Examples

##### Register Queries

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

##### Field Queries

```sql
-- View all fields for a specific register (with descriptions and definitions)
SELECT
    field_name,
    field_position,
    field_width,
    field_description,
    field_definition
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

-- Join registers and fields for complete view (with descriptions and definitions)
SELECT
    r.feature_name,
    r.register_name,
    r.long_name,
    f.field_name,
    f.field_position,
    f.field_width,
    f.field_description,
    f.field_definition
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

-- Find all RES0 (Reserved, must be zero) fields
SELECT
    register_name,
    field_name,
    field_position,
    field_width
FROM aarch64_sysreg_fields
WHERE field_definition = 'RES0'
ORDER BY register_name, field_msb DESC;

-- Count field definitions across all registers
SELECT
    field_definition,
    COUNT(*) as count
FROM aarch64_sysreg_fields
GROUP BY field_definition
ORDER BY count DESC;
```

### Release Information

#### Version 2025.11

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

---

## ISA Database

### Getting Started

#### Prerequisites

- Python 3.8 or later
- DuckDB Python module: `pip install duckdb`

#### Database Generation

##### Step 1: Download and Extract Source Specifications

Download the ARM A-profile ISA specifications from ARM Developer:

```bash
# Download ISA XML (2025-09 ASL1)
# See source_202509/README.md for download links

# Extract to source_202509/
tar -xzf ISA_A64_xml_A_profile-2025-09_ASL1.tar.gz -C source_202509/
```

##### Step 2: Generate the Database

Run the database generator script:

```bash
python gen_aarch64_isa_db.py
```

**What the script does:**
1. Scans `source_202509/ISA_A64_xml_A_profile_FAT-2025-09_ASL1/` for `*.xml` files
2. Parses each XML file to extract:
   - Instruction details (Mnemonic, Title, Description, Class)
   - Encoding variants (32-bit, 64-bit, etc.)
   - Bit field layouts (sf, op, Rn, Rd, imm, etc.)
3. Generates `aarch64_isa_db.duckdb` with ~2300 instructions and ~4600 encodings
4. Exports data to `aarch64_isa_db.xlsx`

### Database Schema

The database contains three main tables: `aarch64_isa_instructions`, `aarch64_isa_encodings`, and `aarch64_isa_encoding_fields`.

#### Table: `aarch64_isa_instructions`

This table stores high-level information about each instruction.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `INTEGER` | Primary Key. Unique identifier for the instruction. |
| `xml_filename` | `VARCHAR` | The name of the source XML file. |
| `mnemonic` | `VARCHAR` | The instruction mnemonic (e.g., `ADD`). |
| `title` | `VARCHAR` | The full title of the instruction (e.g., `ADD (immediate)`). |
| `description` | `VARCHAR` | A brief description of the instruction's operation. |
| `instr_class` | `VARCHAR` | The class of the instruction (e.g., `general`, `float`, `sve`). |
| `isa` | `VARCHAR` | The Instruction Set Architecture (always `A64`). |
| `feature_name` | `VARCHAR` | The feature(s) required for this instruction (e.g., `FEAT_SVE`, `AARCH64`). |
| `exception_level` | `VARCHAR` | The Exception Level(s) where this instruction is available (default `ALL`). |
| `docvars` | `JSON` | A JSON object containing all document variables from the source XML. |

#### Table: `aarch64_isa_encodings`

This table stores the specific encoding variants for each instruction, including the 32-bit field layout.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `INTEGER` | Primary Key. Unique identifier for the encoding. |
| `instruction_id` | `INTEGER` | Foreign Key referencing `aarch64_isa_instructions.id`. |
| `encoding_name` | `VARCHAR` | The internal name of the encoding (e.g., `ADD_32_addsub_imm`). |
| `encoding_label` | `VARCHAR` | A human-readable label for the encoding (e.g., `32-bit`). |
| `iclass_name` | `VARCHAR` | The instruction class name this encoding belongs to. |
| `asm_template` | `VARCHAR` | The assembly syntax template (e.g., `ADD <Wd>, <Wn>, #<imm>`). |
| `bitdiffs` | `VARCHAR` | A string describing the bit differences that distinguish this encoding. |
| `bit_31` ... `bit_0` | `VARCHAR` | The 32 columns representing the instruction encoding from MSB to LSB. Values are '0', '1', or the field name (e.g., 'Rn'). |

#### [REMOVED] Table: `aarch64_isa_encoding_fields`

*This table has been removed in favor of the flattened `bit_31`...`bit_0` columns in `aarch64_isa_encodings`.*

### Usage Examples

#### Querying Instructions by Feature

```sql
-- Find all SVE instructions
SELECT mnemonic, title, feature_name
FROM aarch64_isa_instructions
WHERE feature_name LIKE '%FEAT_SVE%';
```

#### Querying Encodings

```sql
-- Get encodings for a specific instruction
SELECT e.encoding_name, e.asm_template
FROM aarch64_isa_encodings e
JOIN aarch64_isa_instructions i ON e.instruction_id = i.id
WHERE i.mnemonic = 'ADD' AND i.title LIKE '%immediate%';
```
