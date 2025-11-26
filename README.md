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
2. [Getting Started](#getting-started)
3. [System Register Database](#system-register-database)
4. [ISA Database](#isa-database)
5. [Common Operations](#common-operations)

---

## Getting Started

### Prerequisites

- **Python**: 3.8 or later
- **Required Python modules**:
  - `duckdb>=0.8.0,<2.0.0`
  - `pandas>=1.3.0,<3.0.0`
  - `openpyxl>=3.0.9,<4.0.0`

### Installation & Setup

#### Step 1: Download and Extract Source Specifications

Download the ARM A-profile specifications from ARM Developer:

```bash
# Download SysReg XML (2025-09 ASL1) for System Register Database
# Download ISA_A64 XML (2025-09 ASL1) for ISA Database
# See source_202509/README.md for download links

# Extract to source_202509/
tar -xzf SysReg_xml_A_profile-2025-09_ASL1.tar.gz -C source_202509/
tar -xzf ISA_A64_xml_A_profile-2025-09_ASL1.tar.gz -C source_202509/
```

#### Step 2: Set Up Python Environment

Create a virtual environment and install dependencies:

```bash
# Create requirements.txt
cat << EOF > requirements.txt
duckdb>=0.8.0,<2.0.0
pandas>=1.3.0,<3.0.0
openpyxl>=3.0.9,<4.0.0
EOF

# Set up virtual environment
python -m venv myenv && source myenv/bin/activate && pip install --upgrade pip && \
pip install -r requirements.txt
```

#### Step 3: Generate Databases

```bash
# Generate System Register Database
python gen_aarch64_sysreg_db.py

# Generate ISA Database
python gen_aarch64_isa_db.py
```

---

## System Register Database

### Overview

The System Register Database (`aarch64_sysreg_db.duckdb`) provides comprehensive reference data for AArch64 system registers, including:
- 684 feature-register mappings
- 90 unique ARM architecture features (FEAT_*)
- 646 unique system registers
- Detailed bit-field information for each register

### Database Generation

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
6. Automatically exports the database to `aarch64_sysreg_db.xlsx` (3 sheets: registers, fields, joined view)

### Using Query Agent (Recommended)

The `query_register.py` script provides a convenient command-line interface to query registers and fields. The CLI now uses explicit options instead of a single positional argument:

- `--reg <REG>` (or `-r`): Register-style queries. Accepts the same formats as before: `HCR_EL2[1]`, `HCR_EL2[31:8]`, `HCR_EL2.TGE`, or `HCR_EL2`.
- `--name <FIELD_NAME>` (or `-n`): Show all registers that contain the specified field name.
- `--fielddef <DEF>` (or `-f`): Find fields by definition. Allowed values: `RES0`, `RES1`, `UNPREDICTABLE`, `UNDEFINED`, `RAO`, `UNKNOWN`.
- `--json`: Optional flag to output results in JSON format for any of the above options.
 - `--feat <FEAT_NAME>` (or `-F`): Show register names that belong to the given architecture feature (e.g., `FEAT_AA64`, `FEAT_SVE`). If you pass `LIST` it prints all `FEAT_*` names registered in the database.

Examples:

```bash
# Single bit query
python3 query_register.py --reg 'HCR_EL2[1]'

# Bit range query
python3 query_register.py --reg 'HCR_EL2[31:8]'

# Register + field query
python3 query_register.py --reg 'HCR_EL2.TGE'

# Entire register
python3 query_register.py --reg 'ACCDATA_EL1'

# Find registers containing a field named 'TGE'
python3 query_register.py --name TGE

# Find all RES0 fields (text output)
python3 query_register.py --fielddef RES0

# Find all RES0 fields and get JSON output
python3 query_register.py --fielddef RES0 --json
```

Supported query formats for `--reg`:
- `REGISTER_NAME[bit]` - Query specific bit position (e.g., `HCR_EL2[1]`)
- `REGISTER_NAME[high:low]` - Query bit range (e.g., `HCR_EL2[31:8]`)
- `REGISTER_NAME.FIELD` - Query by field name (e.g., `HCR_EL2.TGE`)
- `REGISTER_NAME.FIELD[range]` - Query with field verification (e.g., `TRCIDR12.NUMCONDKEY[31:0]`)
- `REGISTER_NAME` - Query entire register (e.g., `ALLINT`)

The `--name` option searches for a field name across all registers (e.g., `NUMCONDKEY`, `AES`).

The `--fielddef` option searches for fields with a specific field definition value (one of `RES0`, `RES1`, `UNPREDICTABLE`, `UNDEFINED`, `RAO`, `UNKNOWN`) and prints matches in `REGISTER_NAME.FIELD[POSITION]` format (or JSON when `--json` is used).

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

For more query examples and usage with DuckDB CLI or Python API, see the [Common Operations](#common-operations) section.

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

### Overview

The ISA Database (`aarch64_isa_db.duckdb`) provides comprehensive reference data for AArch64 A64 instructions, including:
- ~2300 unique instructions
- ~4600 instruction encodings
- Detailed bit field layouts for each encoding
- Feature mappings (FEAT_*)

### Database Generation

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

### Using Query Agent (Recommended)

The `query_isa.py` script provides a convenient command-line interface to query instructions and encodings:

```bash
# Query encoding pattern(s) for a mnemonic
python3 query_isa.py --n ADD

# Decode opcode to mnemonic and operands
python3 query_isa.py --op 0x91000000
python3 query_isa.py --op 0x91_00_00_00                              # With separators
python3 query_isa.py --op 0b10010001_00000000_00000000_00000000

# Find matching instructions for partial opcode (use X/x for don't care)
python3 query_isa.py --hint 0x9100XXXX                               # X in hex = 4 don't care bits
python3 query_isa.py --hint 0x91_00_XX_XX                            # With separators
python3 query_isa.py --hint 0x9x00xxxx                               # x in hex = 4 don't care bits (same as X)
python3 query_isa.py --hint 0b1001xxxx_0000xxxx_xxxxxxxx_xxxxxxxx    # x in binary = 1 don't care bit

# Show help message
python3 query_isa.py --help
```

**Supported Query Formats:**
- `--n MNEMONIC` - Show encoding pattern(s) for mnemonic (e.g., `ADD`, `MOV`, `NOP`)
- `--op OPCODE` - Decode opcode to mnemonic and operand values (format: `0xHEX` or `0bBINARY`)
- `--hint PARTIAL_OPCODE` - Find matching instructions for partial opcode with `X`/`x` for don't care bits

**Separator Characters (Optional):**
- `_` or `:` can be used as 8-bit separators for better readability
- Examples: `0x91_00_00_00`, `0x91:00:00:00`, `0b10010001_00000000_00000000_00000000`
- Works with both hex and binary formats, and with don't care notation (e.g., `0x91_00_XX_XX`)
- Separators are completely optional and ignored during parsing

**Don't Care Notation for `--hint`:**
- **Hex format**: `X` or `x` = 4 binary don't care bits (e.g., `0x9X00` = `1001XXXX00000000...`)
- **Binary format**: `X` or `x` = 1 binary don't care bit (e.g., `0b1001xxxx` = `1001XXXX`)
- Mixed usage is allowed (e.g., `0x9X0x`, `0x91_00_Xx_XX`)

**Example Outputs:**

```bash
# Query by mnemonic
$ python3 query_isa.py --n NOP
================================================================================
Mnemonic: NOP
Title: NOP -- A64
Features: AARCH64
================================================================================

[1] Encoding: NOP_HI_hints
    Assembly: NOP
    Binary Pattern:  1101 0101 0000 0011 0010 0000 0001 1111
    Hex Pattern:     0xd503201f
    Bit Fields:
      [31:0] = 11010101000000110010000000011111 (all fixed bits)
```

```bash
# Decode opcode
$ python3 query_isa.py --op 0x91000000
ADD x0, x0, #0x0
MOV x0, x0

$ python3 query_isa.py --op 0x910083e0
ADD x0, sp, #0x20

$ python3 query_isa.py --op 0xd503201f
AUTIB1716
PACIB1716
PACIA1716
AUTIA1716
NOP
HINT #0x0
```

```bash
# Partial opcode matching
$ python3 query_isa.py --hint 0x9100XXXX
ADD  <Xd|SP>, <Xn|SP>, #<imm>{, <shift>}
MOV  <Xd|SP>, <Xn|SP>

$ python3 query_isa.py --hint 0xd503201f
AUTIB1716
PACIB1716
PACIA1716
AUTIA1716
NOP
HINT  #<imm>
```

For more query examples and usage with DuckDB CLI or Python API, see the [Common Operations](#common-operations) section.

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

---

## Common Operations

This section covers common operations that apply to both the System Register Database and ISA Database.

### Using DuckDB CLI

```bash
# Open a database
duckdb aarch64_sysreg_db.duckdb
# or
duckdb aarch64_isa_db.duckdb

# Example queries for System Register Database
SELECT COUNT(*) FROM aarch64_sysreg;
SELECT feature_name, register_name FROM aarch64_sysreg LIMIT 10;

# Example queries for ISA Database
SELECT COUNT(*) FROM aarch64_isa_instructions;
SELECT mnemonic, title FROM aarch64_isa_instructions LIMIT 10;
```

### Using Python API

```python
import duckdb

# Connect to System Register Database
conn = duckdb.connect('aarch64_sysreg_db.duckdb')
result = conn.execute("""
    SELECT feature_name, register_name, long_name
    FROM aarch64_sysreg
    WHERE feature_name LIKE 'FEAT_SVE%'
""").fetchall()
for row in result:
    print(f"{row[0]:25s} {row[1]:20s} {row[2]}")
conn.close()

# Connect to ISA Database
conn = duckdb.connect('aarch64_isa_db.duckdb')
result = conn.execute("""
    SELECT mnemonic, title, feature_name
    FROM aarch64_isa_instructions
    WHERE feature_name LIKE '%FEAT_SVE%'
    LIMIT 10
""").fetchall()
for row in result:
    print(f"{row[0]:10s} {row[1]:40s} {row[2]}")
conn.close()
```

### Using Docker

You can use Docker for both database generation and querying without installing Python or DuckDB locally.

#### Generate Databases with Docker

```bash
# Pull Python 3 Docker image
docker pull python:3.11-slim

# Generate System Register Database
docker run --rm -v $(pwd):/workspace -w /workspace python:3.11-slim bash -c "
  pip install --quiet duckdb pandas openpyxl lxml &&
  python gen_aarch64_sysreg_db.py
"

# Generate ISA Database
docker run --rm -v $(pwd):/workspace -w /workspace python:3.11-slim bash -c "
  pip install --quiet duckdb pandas openpyxl lxml &&
  python gen_aarch64_isa_db.py
"

# For Windows PowerShell, use ${PWD} instead of $(pwd)
# For Windows CMD, use %cd% instead of $(pwd)
```

#### Query with DuckDB CLI via Docker

```bash
# Pull official DuckDB Docker image
docker pull duckdb/duckdb:latest

# Interactive SQL shell for System Register Database
docker run -it --rm -v $(pwd):/data duckdb/duckdb:latest /data/aarch64_sysreg_db.duckdb

# Interactive SQL shell for ISA Database
docker run -it --rm -v $(pwd):/data duckdb/duckdb:latest /data/aarch64_isa_db.duckdb

# Run a single query
docker run --rm -v $(pwd):/data duckdb/duckdb:latest /data/aarch64_sysreg_db.duckdb \
  -c "SELECT COUNT(*) as total_rows FROM aarch64_sysreg"

docker run --rm -v $(pwd):/data duckdb/duckdb:latest /data/aarch64_isa_db.duckdb \
  -c "SELECT COUNT(*) as total_instructions FROM aarch64_isa_instructions"
```

### Query Examples

#### System Register Database Queries

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

-- View all fields for a specific register
SELECT
    field_name,
    field_position,
    field_width,
    field_description,
    field_definition
FROM aarch64_sysreg_fields
WHERE register_name = 'ALLINT'
ORDER BY field_msb DESC;

-- Find all RES0 fields
SELECT
    register_name,
    field_name,
    field_position,
    field_width
FROM aarch64_sysreg_fields
WHERE field_definition = 'RES0'
ORDER BY register_name, field_msb DESC;
```

#### ISA Database Queries

```sql
-- Find all SVE instructions
SELECT mnemonic, title, feature_name
FROM aarch64_isa_instructions
WHERE feature_name LIKE '%FEAT_SVE%';

-- Get encodings for a specific instruction
SELECT e.encoding_name, e.asm_template
FROM aarch64_isa_encodings e
JOIN aarch64_isa_instructions i ON e.instruction_id = i.id
WHERE i.mnemonic = 'ADD' AND i.title LIKE '%immediate%';

-- Count instructions per feature
SELECT feature_name, COUNT(*) as instruction_count
FROM aarch64_isa_instructions
GROUP BY feature_name
ORDER BY instruction_count DESC;
```

### Exporting to Excel

Both databases automatically export to Excel format during generation:
- `aarch64_sysreg_db.xlsx` - System Register Database
- `aarch64_isa_db.xlsx` - ISA Database

You can also export manually using DuckDB:

```bash
duckdb aarch64_sysreg_db.duckdb \
  -c "COPY (SELECT * FROM aarch64_sysreg) TO 'output.xlsx' WITH (FORMAT GDAL, DRIVER 'XLSX')"

duckdb aarch64_isa_db.duckdb \
  -c "COPY (SELECT * FROM aarch64_isa_instructions) TO 'output.xlsx' WITH (FORMAT GDAL, DRIVER 'XLSX')"
```
