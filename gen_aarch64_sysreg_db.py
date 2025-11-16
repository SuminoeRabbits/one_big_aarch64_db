#!/usr/bin/env python3
"""
Generate AArch64 System Register Database from ARM XML Specifications

This script parses the ARM A-profile System Register XML specifications
(AArch64-*.xml files only) and creates a DuckDB database.

Database Schema:
- Column 1 (feature_name): ARM Architecture Feature (FEAT_*)
- Column 2 (register_name): System Register Short Name (e.g., ACCDATA_EL1)
- Additional columns: metadata from ARM XML specifications
"""

import os
import sys
import re
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Set
import duckdb

# Check Python version (requires Python 3.9 or higher)
if sys.version_info < (3, 9):
    print("ERROR: This script requires Python 3.9 or higher.")
    print(f"Current version: Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    sys.exit(1)

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

        # Extract field information count and details
        fields = self.root.findall('.//field[@id]')
        reg_data['field_count'] = len(fields)

        # Extract detailed field information (for separate fields table)
        reg_data['fields'] = self._extract_field_info()

        # Extract access types
        access_types = set()
        for access in self.root.findall('.//reg_access_type'):
            if access.text:
                access_types.add(access.text)
        reg_data['access_types'] = ','.join(sorted(access_types)) if access_types else None

        return reg_data

    def _extract_field_info(self) -> List[Dict]:
        """
        Extract field names, bit positions, and descriptions from the register XML.
        Returns a list of field dictionaries sorted by MSB (most significant bit) in descending order.

        Example output:
        [
            {'name': 'RES0', 'msb': 63, 'lsb': 14, 'width': 50, 'position': '[63:14]', 'description': 'Reserved, RES0.'},
            {'name': 'ALLINT', 'msb': 13, 'lsb': 13, 'width': 1, 'position': '[13:13]', 'description': 'All interrupt mask...'},
            {'name': 'RES0', 'msb': 12, 'lsb': 0, 'width': 13, 'position': '[12:0]', 'description': 'Reserved, RES0.'}
        ]
        """
        fields_list = []

        # Find all field elements with id attribute
        for field in self.root.findall('.//field[@id]'):
            field_name_elem = field.find('field_name')
            field_msb_elem = field.find('field_msb')
            field_lsb_elem = field.find('field_lsb')

            # Get field name - use rwtype if field_name is not available (for reserved fields)
            if field_name_elem is not None and field_name_elem.text:
                field_name = field_name_elem.text.strip()
            else:
                # For reserved fields, use rwtype (e.g., RES0, RES1)
                rwtype = field.get('rwtype', 'UNKNOWN')
                field_name = rwtype

            # Get field description from <field_description> elements
            field_description = self._extract_field_description(field)

            # Get bit positions
            if field_msb_elem is not None and field_lsb_elem is not None:
                try:
                    msb = int(field_msb_elem.text.strip())
                    lsb = int(field_lsb_elem.text.strip())
                    width = msb - lsb + 1

                    fields_list.append({
                        'name': field_name,
                        'msb': msb,
                        'lsb': lsb,
                        'width': width,
                        'position': f'[{msb}:{lsb}]',
                        'description': field_description
                    })
                except (ValueError, AttributeError):
                    # Skip fields with invalid bit positions
                    pass

        # Sort by MSB in descending order (highest bit first)
        fields_list.sort(key=lambda x: x['msb'], reverse=True)

        return fields_list

    def _extract_field_description(self, field_element) -> str:
        """
        Extract field description from <field_description> elements.
        Concatenates all <para> text from all <field_description> elements.

        Args:
            field_element: The field XML element

        Returns:
            Concatenated description text, or None if no description found
        """
        descriptions = []

        # Find all field_description elements
        for desc_elem in field_element.findall('field_description'):
            # Extract all <para> text within this field_description
            for para in desc_elem.findall('.//para'):
                # Get all text content from para element (including child elements)
                para_text_parts = []

                # Get the initial text
                if para.text:
                    para_text_parts.append(para.text.strip())

                # Get text from child elements and their tails
                for child in para:
                    if child.text:
                        para_text_parts.append(child.text.strip())
                    if child.tail:
                        para_text_parts.append(child.tail.strip())

                # Join all parts and add to descriptions
                full_text = ' '.join(part for part in para_text_parts if part)
                if full_text:
                    descriptions.append(full_text)

        # Join all descriptions with space
        if descriptions:
            return ' '.join(descriptions)
        else:
            return None

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
    """DuckDB Database for AArch64 System Registers"""

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

        # Fields table - detailed bit-field information
        self.conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS aarch64_sysreg_fields_id_seq START 1
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS aarch64_sysreg_fields (
                "id" INTEGER PRIMARY KEY DEFAULT nextval('aarch64_sysreg_fields_id_seq'),
                "register_name" VARCHAR NOT NULL,
                "field_name" VARCHAR NOT NULL,
                "field_msb" INTEGER NOT NULL,
                "field_lsb" INTEGER NOT NULL,
                "field_width" INTEGER NOT NULL,
                "field_position" VARCHAR NOT NULL,
                "field_description" VARCHAR,
                "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index for faster field queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fields_register
            ON aarch64_sysreg_fields("register_name")
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fields_name
            ON aarch64_sysreg_fields("field_name")
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

    def clear_fields_for_register(self, register_name: str):
        """Clear all existing fields for a register before inserting new ones"""
        self.conn.execute("""
            DELETE FROM aarch64_sysreg_fields
            WHERE "register_name" = ?
        """, [register_name])

    def insert_fields(self, register_name: str, fields: List[Dict]) -> int:
        """
        Insert field information for a register into the fields table.
        Clears any existing fields for the register first to avoid duplicates.

        Args:
            register_name: The register name
            fields: List of field dictionaries with 'name', 'msb', 'lsb', 'width', 'position', 'description'

        Returns: Number of fields inserted
        """
        if not fields:
            return 0

        # Clear existing fields for this register to avoid duplicates
        self.clear_fields_for_register(register_name)

        inserted_count = 0
        for field in fields:
            try:
                self.conn.execute("""
                    INSERT INTO aarch64_sysreg_fields (
                        "register_name", "field_name", "field_msb", "field_lsb",
                        "field_width", "field_position", "field_description"
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [
                    register_name,
                    field['name'],
                    field['msb'],
                    field['lsb'],
                    field['width'],
                    field['position'],
                    field.get('description')  # Use .get() to handle fields without description
                ])
                inserted_count += 1
            except Exception as e:
                print(f"    WARNING: Could not insert field {field['name']} for {register_name} - {e}")

        return inserted_count

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
    total_fields = 0
    processed_registers = set()  # Track unique registers for field insertion

    for i, xml_file in enumerate(xml_files, 1):
        try:
            parser = SysRegParser(xml_file)
            reg_data = parser.parse_register()

            if reg_data:
                inserted_ids = db.insert_register(reg_data)
                success_count += 1
                total_rows += len(inserted_ids)

                # Insert fields only once per unique register (not per feature)
                register_name = reg_data['register_name']
                if register_name not in processed_registers:
                    fields = reg_data.get('fields', [])
                    if fields:
                        field_count = db.insert_fields(register_name, fields)
                        total_fields += field_count
                    processed_registers.add(register_name)

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
    print(f"  Register rows created:    {total_rows}")
    print(f"  Field rows created:       {total_fields}")
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

    # Count total fields
    result = db.conn.execute("""
        SELECT COUNT(*) as total_fields
        FROM aarch64_sysreg_fields
    """).fetchone()
    print(f"  Total fields:             {result[0]}")

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
