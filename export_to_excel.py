#!/usr/bin/env python3
"""
Export AArch64 System Register Database to Excel

This script exports the DuckDB database to an Excel file with multiple sheets.
Each sheet contains different views of the data for easy analysis.
"""

import sys
from pathlib import Path
import duckdb
import pandas as pd

# Check Python version (requires Python 3.9 or higher)
if sys.version_info < (3, 9):
    print("ERROR: This script requires Python 3.9 or higher.")
    print(f"Current version: Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    sys.exit(1)

# Database file
DB_FILE = Path(__file__).parent / "aarch64_sysreg_db.duckdb"
EXCEL_FILE = Path(__file__).parent / "aarch64_sysreg_db.xlsx"


def export_to_excel():
    """Export database to Excel with multiple sheets"""

    if not DB_FILE.exists():
        print(f"ERROR: Database file not found: {DB_FILE}")
        print("Please run gen_aarch64_sysreg_db.py first to generate the database.")
        sys.exit(1)

    print("=" * 80)
    print("AArch64 System Register Database - Excel Export")
    print("=" * 80)
    print()
    print(f"Database: {DB_FILE}")
    print(f"Output:   {EXCEL_FILE}")
    print()

    # Connect to database
    conn = duckdb.connect(str(DB_FILE))

    # Get statistics
    reg_count = conn.execute("SELECT COUNT(*) FROM aarch64_sysreg").fetchone()[0]
    field_count = conn.execute("SELECT COUNT(*) FROM aarch64_sysreg_fields").fetchone()[0]

    print("Creating Excel file with 3 sheets...")
    print()

    # Export to Excel with multiple sheets
    with pd.ExcelWriter(str(EXCEL_FILE), engine='openpyxl') as writer:
        # Sheet 1: Main register table
        print(f"  [1/3] Exporting 'registers' sheet ({reg_count} rows)...")
        df_registers = conn.execute('SELECT * FROM aarch64_sysreg').df()
        df_registers.to_excel(writer, sheet_name='registers', index=False)

        # Sheet 2: Fields table
        print(f"  [2/3] Exporting 'fields' sheet ({field_count} rows)...")
        df_fields = conn.execute('SELECT * FROM aarch64_sysreg_fields').df()
        df_fields.to_excel(writer, sheet_name='fields', index=False)

        # Sheet 3: Joined view (register + fields)
        print(f"  [3/3] Exporting 'registers_with_fields' sheet (joined view)...")
        df_joined = conn.execute("""
            SELECT
                r.feature_name,
                r.register_name,
                r.long_name,
                r.register_width,
                r.field_count,
                f.field_name,
                f.field_msb,
                f.field_lsb,
                f.field_width,
                f."field_position"
            FROM aarch64_sysreg r
            LEFT JOIN aarch64_sysreg_fields f ON r.register_name = f.register_name
            ORDER BY r.register_name, f.field_msb DESC
        """).df()
        df_joined.to_excel(writer, sheet_name='registers_with_fields', index=False)

    conn.close()

    print()
    print("=" * 80)
    print("Export completed successfully!")
    print("=" * 80)
    print()
    print(f"Excel file: {EXCEL_FILE}")
    print()
    print("Sheets included:")
    print(f"  1. 'registers'             - {reg_count} feature-register mappings")
    print(f"  2. 'fields'                - {field_count} bit-field definitions")
    print(f"  3. 'registers_with_fields' - Joined view for analysis")
    print()


if __name__ == "__main__":
    export_to_excel()
