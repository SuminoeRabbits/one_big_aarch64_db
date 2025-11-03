#!/usr/bin/env python3
"""
Generate AArch64 System Register Database from ARM XML Specifications

This script parses the ARM A-profile System Register XML specifications
(AArch64-*.xml files only) and creates a DuckDB database for tracking test coverage.

Database Schema:
- Column 1 (feature_name): ARM Architecture Feature (FEAT_*)
- Column 2 (register_name): System Register Short Name (e.g., ACCDATA_EL1)
- Additional columns: metadata and test coverage information
"""

import os
import sys
import re
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Set
import duckdb

# Define PROJECT_DIR: the directory containing system register XML files
PROJECT_DIR = Path(os.getcwd()) / "source_202509" / "SysReg_xml_A_profile-2025-09_ASL1"

# Output database name: aarch64_sysreg_db.duckdb
DB_NAME = "aarch64_sysreg_db.duckdb"
OUTPUT_DB = Path(os.getcwd()) / DB_NAME

# Features to exclude (baseline features that should be ignored, except when they are the ONLY feature)
# FEAT_AA32: AArch32 compatibility feature (should be extracted only from reg_condition, not fields_condition)
# Note: FEAT_AA64 is excluded only when other features exist; if it's the only feature, we keep it
EXCLUDED_FEATURES_BASE = {'FEAT_AArch64', 'FEAT_AA32'}
FEAT_AA64 = 'FEAT_AA64'


class SysRegParser:
    """Parser for ARM System Register XML files (AArch64 only)"""

    def __init__(self, xml_path: Path):
        self.xml_path = xml_path
        self.tree = ET.parse(xml_path)
        self.root = self.tree.getroot()

    def is_aarch64_register(self) -> bool:
        """Check if this is an AArch64 register"""
        register = self.root.find('.//register')
        if register is None:
            return False

        exec_state = register.get('execution_state', '')
        return exec_state == 'AArch64'

    def parse_register(self) -> Optional[Dict]:
        """Parse a single AArch64 register XML file and extract key information"""
        register = self.root.find('.//register')
        if register is None:
            return None

        # Check if this is an actual AArch64 register (not a stub)
        is_register = register.get('is_register', 'False') == 'True'
        is_stub = register.get('is_stub_entry', 'False') == 'True'
        exec_state = register.get('execution_state', '')

        if not is_register or is_stub or exec_state != 'AArch64':
            return None

        # Extract register short name
        short_name = self._get_text('.//reg_short_name')
        if not short_name:
            return None

        # Extract basic register information
        reg_data = {
            'xml_filename': self.xml_path.name,
            'register_name': short_name,
            'long_name': self._get_text('.//reg_long_name'),
            'is_internal': register.get('is_internal', 'False'),
            'reg_condition': self._get_text('.//reg_condition'),
            'reg_purpose': self._get_text('.//reg_purpose//purpose_text//para'),
        }

        # Extract register groups
        groups = self.root.findall('.//reg_groups//reg_group')
        reg_data['reg_groups'] = ','.join([g.text for g in groups if g.text])

        # Extract register width/length
        fieldsets = self.root.findall('.//fields[@length]')
        if fieldsets:
            lengths = [fs.get('length') for fs in fieldsets]
            reg_data['register_width'] = ','.join(set(lengths))
        else:
            reg_data['register_width'] = None

        # Extract architecture features (FEAT_* conditions) - PRIMARY EXTRACTION
        reg_data['features'] = self._extract_features()

        # Extract field information count
        fields = self.root.findall('.//field[@id]')
        reg_data['field_count'] = len(fields)

        # Extract access types
        access_types = set()
        for access in self.root.findall('.//reg_access_type'):
            if access.text:
                access_types.add(access.text)
        reg_data['access_types'] = ','.join(sorted(access_types)) if access_types else None

        return reg_data

    def _extract_features(self) -> Set[str]:
        """
        Extract FEAT_* features from the register XML.
        Primary source: reg_condition element only

        Special handling:
        - If only FEAT_AA64 is found, keep it (indicates baseline AArch64 register)
        - If FEAT_AA64 + other features are found, remove FEAT_AA64 (other features are more specific)
        - FEAT_AA32 is always excluded (AArch32 field-level feature)

        Note: We only extract from reg_condition, not from fields_condition,
        because fields_condition describes per-field implementation requirements,
        not register-level requirements.
        """
        features = set()

        # Extract ONLY from reg_condition (register-level implementation condition)
        reg_condition = self._get_text('.//reg_condition')
        if reg_condition:
            feat_matches = re.findall(r'FEAT_\w+', reg_condition)
            features.update(feat_matches)

        # Remove baseline excluded features (except FEAT_AA64 for now)
        features = features - EXCLUDED_FEATURES_BASE

        # Special handling for FEAT_AA64:
        # - If FEAT_AA64 is the ONLY feature, keep it
        # - If there are other features besides FEAT_AA64, remove FEAT_AA64
        if FEAT_AA64 in features:
            if len(features) > 1:
                # Other features exist, remove FEAT_AA64
                features.discard(FEAT_AA64)
            # else: FEAT_AA64 is the only feature, keep it

        return features

    def _get_text(self, xpath: str, default: str = None) -> Optional[str]:
        """Helper to safely extract text from XML element"""
        element = self.root.find(xpath)
        if element is not None and element.text:
            return element.text.strip()
        return default


class SysRegDatabase:
    """DuckDB Database for AArch64 System Register Coverage"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = duckdb.connect(str(db_path))
        self._create_schema()

    def _create_schema(self):
        """
        Create database schema for AArch64 system registers

        Main table structure:
        - Column 1: feature_name (FEAT_*)
        - Column 2: register_name (short name like ACCDATA_EL1)
        - Additional columns: metadata
        """
        # Main register-feature mapping table
        self.conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS aarch64_sysreg_id_seq START 1
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS aarch64_sysreg (
                id INTEGER PRIMARY KEY DEFAULT nextval('aarch64_sysreg_id_seq'),
                feature_name VARCHAR NOT NULL,
                register_name VARCHAR NOT NULL,
                xml_filename VARCHAR NOT NULL,
                long_name VARCHAR,
                is_internal VARCHAR,
                reg_condition VARCHAR,
                reg_purpose VARCHAR,
                reg_groups VARCHAR,
                register_width VARCHAR,
                field_count INTEGER,
                access_types VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(feature_name, register_name)
            )
        """)

        # Create index for faster queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_feature
            ON aarch64_sysreg(feature_name)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_register
            ON aarch64_sysreg(register_name)
        """)

        # Coverage tracking table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS coverage_status (
                register_id INTEGER,
                test_suite VARCHAR,
                test_name VARCHAR,
                coverage_status VARCHAR CHECK(coverage_status IN ('untested', 'partial', 'full')),
                last_tested TIMESTAMP,
                notes VARCHAR,
                PRIMARY KEY (register_id, test_suite, test_name),
                FOREIGN KEY (register_id) REFERENCES aarch64_sysreg(id)
            )
        """)

        # Metadata table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key VARCHAR PRIMARY KEY,
                value VARCHAR,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    def insert_register(self, reg_data: Dict) -> List[int]:
        """
        Insert a system register into the database.
        If the register has multiple features, create one row per feature.
        If no features are found, create a row with feature_name='NO_FEATURE'

        Returns: List of inserted row IDs
        """
        inserted_ids = []
        features = reg_data.get('features', set())

        # If no features found, still insert with a placeholder
        if not features:
            features = {'NO_FEATURE'}

        for feature in features:
            try:
                # Try to insert
                self.conn.execute("""
                    INSERT INTO aarch64_sysreg (
                        feature_name, register_name, xml_filename, long_name,
                        is_internal, reg_condition, reg_purpose, reg_groups,
                        register_width, field_count, access_types
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (feature_name, register_name) DO UPDATE SET
                        xml_filename = EXCLUDED.xml_filename,
                        long_name = EXCLUDED.long_name,
                        is_internal = EXCLUDED.is_internal,
                        reg_condition = EXCLUDED.reg_condition,
                        reg_purpose = EXCLUDED.reg_purpose,
                        reg_groups = EXCLUDED.reg_groups,
                        register_width = EXCLUDED.register_width,
                        field_count = EXCLUDED.field_count,
                        access_types = EXCLUDED.access_types
                """, [
                    feature,
                    reg_data['register_name'],
                    reg_data['xml_filename'],
                    reg_data['long_name'],
                    reg_data['is_internal'],
                    reg_data['reg_condition'],
                    reg_data['reg_purpose'],
                    reg_data['reg_groups'],
                    reg_data['register_width'],
                    reg_data['field_count'],
                    reg_data['access_types']
                ])

                # Get the ID of the inserted/updated row
                result = self.conn.execute("""
                    SELECT id FROM aarch64_sysreg
                    WHERE feature_name = ? AND register_name = ?
                """, [feature, reg_data['register_name']])

                row = result.fetchone()
                if row:
                    inserted_ids.append(row[0])

            except Exception as e:
                print(f"    WARNING: Could not insert {feature}:{reg_data['register_name']} - {e}")

        return inserted_ids

    def set_metadata(self, key: str, value: str):
        """Set metadata value"""
        self.conn.execute("""
            INSERT INTO metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value
        """, [key, value])
        self.conn.commit()

    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    """Main entry point"""
    print("=" * 80)
    print("AArch64 System Register Database Generator")
    print("=" * 80)
    print()

    # Verify PROJECT_DIR exists
    if not PROJECT_DIR.exists():
        print(f"ERROR: PROJECT_DIR does not exist: {PROJECT_DIR}")
        print(f"Please ensure the SysReg XML files are extracted to this location.")
        sys.exit(1)

    print(f"PROJECT_DIR: {PROJECT_DIR}")
    print(f"OUTPUT_DB:   {OUTPUT_DB}")
    print()

    # Find all AArch64 XML files (AArch64-*.xml pattern)
    xml_files = list(PROJECT_DIR.glob("AArch64-*.xml"))
    print(f"Found {len(xml_files)} AArch64-*.xml files")
    print()

    # Initialize database
    print("Initializing DuckDB database...")
    db = SysRegDatabase(OUTPUT_DB)

    # Set metadata
    db.set_metadata('spec_version', '2025-09')
    db.set_metadata('spec_format', 'ASL1')
    db.set_metadata('architecture', 'AArch64')
    db.set_metadata('source_directory', str(PROJECT_DIR))

    # Parse and insert registers
    print("Parsing AArch64 XML files and populating database...")
    print()

    success_count = 0
    skip_count = 0
    error_count = 0
    total_rows = 0

    for i, xml_file in enumerate(xml_files, 1):
        try:
            parser = SysRegParser(xml_file)
            reg_data = parser.parse_register()

            if reg_data:
                inserted_ids = db.insert_register(reg_data)
                success_count += 1
                total_rows += len(inserted_ids)

                # Show progress for first few and every 100
                if success_count <= 5 or success_count % 100 == 0:
                    features = reg_data.get('features', set())
                    feat_str = ', '.join(sorted(features)) if features else 'NO_FEATURE'
                    print(f"  [{success_count:4d}] {reg_data['register_name']:20s} -> {feat_str}")
            else:
                skip_count += 1

        except Exception as e:
            error_count += 1
            print(f"  ERROR parsing {xml_file.name}: {e}")

    print()
    print("=" * 80)
    print("Summary:")
    print(f"  Total AArch64 XML files:  {len(xml_files)}")
    print(f"  Registers processed:      {success_count}")
    print(f"  Database rows created:    {total_rows}")
    print(f"  Files skipped:            {skip_count}")
    print(f"  Errors:                   {error_count}")
    print("=" * 80)
    print()

    # Display statistics
    print("Database Statistics:")

    # Count unique features
    result = db.conn.execute("""
        SELECT COUNT(DISTINCT feature_name) as unique_features
        FROM aarch64_sysreg
    """).fetchone()
    print(f"  Unique features:          {result[0]}")

    # Count unique registers
    result = db.conn.execute("""
        SELECT COUNT(DISTINCT register_name) as unique_registers
        FROM aarch64_sysreg
    """).fetchone()
    print(f"  Unique registers:         {result[0]}")

    # Top 5 features by register count
    print()
    print("  Top 5 features by register count:")
    results = db.conn.execute("""
        SELECT feature_name, COUNT(*) as reg_count
        FROM aarch64_sysreg
        WHERE feature_name != 'NO_FEATURE'
        GROUP BY feature_name
        ORDER BY reg_count DESC
        LIMIT 5
    """).fetchall()

    for feat, count in results:
        print(f"    {feat:30s} {count:4d} registers")

    print()
    print("=" * 80)
    print()

    # Display sample queries
    print("Database created successfully!")
    print(f"Database name:     {DB_NAME}")
    print(f"Database location: {OUTPUT_DB}")
    print()
    print("Sample queries:")
    print(f"  duckdb {DB_NAME}")
    print("  SELECT COUNT(*) FROM aarch64_sysreg;")
    print("  SELECT feature_name, register_name FROM aarch64_sysreg LIMIT 10;")
    print("  SELECT * FROM aarch64_sysreg WHERE feature_name = 'FEAT_LS64_ACCDATA';")
    print("  SELECT feature_name, COUNT(*) as cnt FROM aarch64_sysreg GROUP BY feature_name ORDER BY cnt DESC;")
    print()

    db.close()
    print("Done!")


if __name__ == "__main__":
    main()
