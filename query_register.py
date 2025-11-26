#!/usr/bin/env python3
"""
AArch64 System Register Query Agent

This script answers questions about AArch64 system registers and their bit fields.

Examples:
    python3 query_register.py "HCR_EL2[1]"      # Query bit position
    python3 query_register.py "HCR_EL2[31:8]"   # Query bit range
    python3 query_register.py "HCR_EL2.TGE"     # Query by field name
    python3 query_register.py "ACCDATA_EL1"     # Query entire register
    python3 query_register.py "RES0"            # Query all RES0 fields
    python3 query_register.py "NUMCONDKEY"      # Query field across all registers
"""

import sys
import re
import json
import argparse
from pathlib import Path
import duckdb

# Check Python version (requires Python 3.9 or higher)
if sys.version_info < (3, 9):
    print("ERROR: This script requires Python 3.9 or higher.")
    print(f"Current version: Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    sys.exit(1)

# Database file
DB_FILE = Path(__file__).parent / "aarch64_sysreg_db.duckdb"


class RegisterQueryAgent:
    """Agent for querying AArch64 system register information"""

    def __init__(self, db_path: Path):
        if not db_path.exists():
            raise FileNotFoundError(
                f"Database not found: {db_path}\n"
                "Please run gen_aarch64_sysreg_db.py first."
            )
        self.conn = duckdb.connect(str(db_path))

    def parse_query(self, query: str) -> dict:
        """
        Parse user query to extract register name and optional bit position/range/field name.

        Examples:
            "HCR_EL2[1]" -> {'register': 'HCR_EL2', 'bit_start': 1, 'bit_end': 1, 'field_name': None, 'verify_field': None, 'field_definition': None, 'field_only': False}
            "HCR_EL2[31:8]" -> {'register': 'HCR_EL2', 'bit_start': 8, 'bit_end': 31, 'field_name': None, 'verify_field': None, 'field_definition': None, 'field_only': False}
            "ACCDATA_EL1" -> {'register': 'ACCDATA_EL1', 'bit_start': None, 'bit_end': None, 'field_name': None, 'verify_field': None, 'field_definition': None, 'field_only': False}
            "HCR_EL2.TGE" -> {'register': 'HCR_EL2', 'bit_start': None, 'bit_end': None, 'field_name': 'TGE', 'verify_field': None, 'field_definition': None, 'field_only': False}
            "RES0" -> {'register': None, 'bit_start': None, 'bit_end': None, 'field_name': None, 'verify_field': None, 'field_definition': 'RES0', 'field_only': False}
            "TRCIDR12.NUMCONDKEY[31:0]" -> {'register': 'TRCIDR12', 'bit_start': 0, 'bit_end': 31, 'field_name': None, 'verify_field': 'NUMCONDKEY', 'field_definition': None, 'field_only': False}
            "NUMCONDKEY" -> {'register': None, 'bit_start': None, 'bit_end': None, 'field_name': 'NUMCONDKEY', 'verify_field': None, 'field_definition': None, 'field_only': True}
        """
        query = query.strip()

        # Pattern 0: Field Definition query (RES0, RES1, UNPREDICTABLE, UNDEFINED, RAO, UNKNOWN)
        allowed_definitions = {'RES0', 'RES1', 'UNPREDICTABLE', 'UNDEFINED', 'RAO', 'UNKNOWN'}
        if query in allowed_definitions:
            return {
                'register': None,
                'bit_start': None,
                'bit_end': None,
                'field_name': None,
                'verify_field': None,
                'field_definition': query,
                'field_only': False
            }

        # Pattern 1: REGISTER.FIELD_NAME[bit_position] or REGISTER.FIELD_NAME[bit_high:bit_low]
        # This pattern should be checked before the simple dot pattern
        dot_bracket_pattern = r'^([A-Z0-9_<>]+)\.([A-Z0-9_]+)\[(\d+)(?::(\d+))?\]$'
        dot_bracket_match = re.match(dot_bracket_pattern, query)

        if dot_bracket_match:
            register_name = dot_bracket_match.group(1)
            field_name = dot_bracket_match.group(2)

            if dot_bracket_match.group(4):
                # Range format: REGISTER.FIELD[high:low]
                bit_high = int(dot_bracket_match.group(3))
                bit_low = int(dot_bracket_match.group(4))
                bit_start = min(bit_high, bit_low)
                bit_end = max(bit_high, bit_low)
            else:
                # Single bit format: REGISTER.FIELD[bit]
                bit_start = int(dot_bracket_match.group(3))
                bit_end = bit_start

            return {
                'register': register_name,
                'bit_start': bit_start,
                'bit_end': bit_end,
                'field_name': None,
                'verify_field': field_name,  # Field name to verify
                'field_definition': None,
                'field_only': False
            }

        # Pattern 2: REGISTER.FIELD_NAME format (without brackets)
        dot_pattern = r'^([A-Z0-9_<>]+)\.([A-Z0-9_]+)$'
        dot_match = re.match(dot_pattern, query)

        if dot_match:
            return {
                'register': dot_match.group(1),
                'bit_start': None,
                'bit_end': None,
                'field_name': dot_match.group(2),
                'verify_field': None,
                'field_definition': None,
                'field_only': False
            }

        # Pattern 3: REGISTER_NAME[bit_position] or REGISTER_NAME[bit_high:bit_low]
        bracket_pattern = r'^([A-Z0-9_<>]+)(?:\[(\d+)(?::(\d+))?\])?$'
        bracket_match = re.match(bracket_pattern, query)

        if not bracket_match:
            return None

        register_name = bracket_match.group(1)

        if bracket_match.group(2):
            if bracket_match.group(3):
                # Range format: [high:low]
                bit_high = int(bracket_match.group(2))
                bit_low = int(bracket_match.group(3))
                # Ensure high >= low
                bit_start = min(bit_high, bit_low)
                bit_end = max(bit_high, bit_low)
            else:
                # Single bit format: [bit]
                bit_start = int(bracket_match.group(2))
                bit_end = bit_start
        else:
            # No bit specification
            bit_start = None
            bit_end = None

        # Check if this might be a field-name-only query
        # Try to find this as a field name in the database
        if bit_start is None and bit_end is None:
            field_search = self.search_field_name(register_name)
            if field_search and len(field_search) > 0:
                # This looks like a field name, not a register name
                return {
                    'register': None,
                    'bit_start': None,
                    'bit_end': None,
                    'field_name': register_name,  # Treat as field name
                    'verify_field': None,
                    'field_definition': None,
                    'field_only': True
                }

        return {
            'register': register_name,
            'bit_start': bit_start,
            'bit_end': bit_end,
            'field_name': None,
            'verify_field': None,
            'field_definition': None,
            'field_only': False
        }

    def search_field_name(self, field_name: str) -> list:
        """
        Search for all registers containing a specific field name.

        Args:
            field_name: Field name to search for

        Returns:
            List of register names containing this field, or empty list if not found
        """
        result = self.conn.execute("""
            SELECT DISTINCT "register_name"
            FROM aarch64_sysreg_fields
            WHERE "field_name" = ?
            ORDER BY "register_name"
        """, [field_name]).fetchall()

        return [row[0] for row in result]

    def query_field_by_name(self, register_name: str, field_name: str, bit_start: int = None, bit_end: int = None) -> dict:
        """
        Query field information by field name.

        Args:
            register_name: Register name (e.g., 'HCR_EL2')
            field_name: Field name (e.g., 'TGE')
            bit_start: Optional bit start position for matching specific field when multiple fields have same name
            bit_end: Optional bit end position for matching specific field when multiple fields have same name

        Returns:
            dict with field information, or None if not found
        """
        # Get register metadata first
        metadata = self.get_register_metadata(register_name)
        if not metadata:
            return None

        # Find the field by name
        result = self.conn.execute("""
            SELECT
                "register_name",
                "field_name",
                "field_msb",
                "field_lsb",
                "field_width",
                "field_position",
                "field_description",
                "field_definition"
            FROM aarch64_sysreg_fields
            WHERE "register_name" = ?
              AND "field_name" = ?
            ORDER BY "field_msb" DESC
        """, [register_name, field_name]).fetchall()

        if not result:
            return None

        # If bit range is specified, find the field that matches the exact bit range
        if bit_start is not None and bit_end is not None:
            for row in result:
                if row[2] == bit_end and row[3] == bit_start:  # field_msb == bit_end and field_lsb == bit_start
                    field = row
                    break
            else:
                # No field matches the exact bit range
                return None
        else:
            # If multiple fields with same name, take the first one (highest MSB)
            field = result[0]

        return {
            'register_name': field[0],
            'features': metadata['features'],
            'long_name': metadata['long_name'],
            'register_width': metadata['register_width'],
            'field_name': field[1],
            'field_msb': field[2],
            'field_lsb': field[3],
            'field_width': field[4],
            'field_position': field[5],
            'field_description': field[6],
            'field_definition': field[7],
            'query_type': 'field_name'
        }

    def get_register_metadata(self, register_name: str) -> dict:
        """
        Get register metadata including feature names and long name.

        Returns:
            dict with register metadata, or None if not found
        """
        # Get all features and metadata for this register
        result = self.conn.execute("""
            SELECT
                feature_name,
                long_name,
                register_width,
                reg_purpose
            FROM aarch64_sysreg
            WHERE register_name = ?
        """, [register_name]).fetchall()

        if not result:
            return None

        # Collect all features for this register
        features = [row[0] for row in result]
        # Use the first row for metadata (should be same across all features)
        first_row = result[0]

        return {
            'register_name': register_name,
            'features': features,
            'long_name': first_row[1],
            'register_width': first_row[2],
            'reg_purpose': first_row[3]
        }

    def query_bit_field(self, register_name: str, bit_position: int) -> dict:
        """
        Query information about a specific bit position in a register.

        Returns:
            dict with field information, or None if not found
        """
        # Get register metadata first
        metadata = self.get_register_metadata(register_name)
        if not metadata:
            return None

        # Find the field that contains this bit position
        result = self.conn.execute("""
            SELECT
                "register_name",
                "field_name",
                "field_msb",
                "field_lsb",
                "field_width",
                "field_position",
                "field_description",
                "field_definition"
            FROM aarch64_sysreg_fields
            WHERE "register_name" = ?
              AND "field_msb" >= ?
              AND "field_lsb" <= ?
            ORDER BY "field_msb" DESC
        """, [register_name, bit_position, bit_position]).fetchall()

        if not result:
            return None

        # Should be exactly one field (unless there are overlapping conditional fields)
        field = result[0]

        return {
            'register_name': field[0],
            'features': metadata['features'],
            'long_name': metadata['long_name'],
            'register_width': metadata['register_width'],
            'field_name': field[1],
            'field_msb': field[2],
            'field_lsb': field[3],
            'field_width': field[4],
            'field_position': field[5],
            'field_description': field[6],
            'field_definition': field[7],
            'bit_position': bit_position
        }

    def query_bit_range(self, register_name: str, bit_start: int, bit_end: int) -> dict:
        """
        Query information about a bit range in a register.
        Returns all fields that overlap with the specified bit range.

        Args:
            register_name: Register name
            bit_start: Start bit position (inclusive, lower value)
            bit_end: End bit position (inclusive, higher value)

        Returns:
            dict with fields that overlap the range, or None if not found
        """
        # Get register metadata first
        metadata = self.get_register_metadata(register_name)
        if not metadata:
            return None

        # Find all fields that overlap with the bit range
        # A field overlaps if: field_lsb <= bit_end AND field_msb >= bit_start
        result = self.conn.execute("""
            SELECT
                "register_name",
                "field_name",
                "field_msb",
                "field_lsb",
                "field_width",
                "field_position",
                "field_description",
                "field_definition"
            FROM aarch64_sysreg_fields
            WHERE "register_name" = ?
              AND "field_lsb" <= ?
              AND "field_msb" >= ?
            ORDER BY "field_msb" DESC
        """, [register_name, bit_end, bit_start]).fetchall()

        if not result:
            return None

        fields = [
            {
                'name': f[1],
                'msb': f[2],
                'lsb': f[3],
                'width': f[4],
                'position': f[5],
                'description': f[6],
                'definition': f[7]
            }
            for f in result
        ]

        return {
            'register_name': register_name,
            'features': metadata['features'],
            'long_name': metadata['long_name'],
            'register_width': metadata['register_width'],
            'bit_start': bit_start,
            'bit_end': bit_end,
            'bit_range': f'[{bit_end}:{bit_start}]',
            'range_width': bit_end - bit_start + 1,
            'fields': fields
        }

    def query_register(self, register_name: str) -> dict:
        """
        Query general information about a register.

        Returns:
            dict with register information, or None if not found
        """
        # Get register metadata including all features
        metadata = self.get_register_metadata(register_name)
        if not metadata:
            return None

        # Get field count from first feature entry
        reg_info = self.conn.execute("""
            SELECT DISTINCT
                field_count
            FROM aarch64_sysreg
            WHERE register_name = ?
            LIMIT 1
        """, [register_name]).fetchone()

        # Get all fields
        fields = self.conn.execute("""
            SELECT
                "field_name",
                "field_msb",
                "field_lsb",
                "field_width",
                "field_position",
                "field_description",
                "field_definition"
            FROM aarch64_sysreg_fields
            WHERE "register_name" = ?
            ORDER BY "field_msb" DESC
        """, [register_name]).fetchall()

        return {
            'register_name': register_name,
            'features': metadata['features'],
            'long_name': metadata['long_name'],
            'register_width': metadata['register_width'],
            'field_count': reg_info[0] if reg_info else 0,
            'reg_purpose': metadata['reg_purpose'],
            'fields': [
                {
                    'name': f[0],
                    'msb': f[1],
                    'lsb': f[2],
                    'width': f[3],
                    'position': f[4],
                    'description': f[5],
                    'definition': f[6]
                }
                for f in fields
            ]
        }

    def query_all_fields_by_name(self, field_name: str) -> list:
        """
        Query all occurrences of a field name across all registers.

        Args:
            field_name: Field name to search for

        Returns:
            List of field information dictionaries, one per register
        """
        # Get all registers containing this field
        registers = self.search_field_name(field_name)

        if not registers:
            return []

        # Query field info for each register
        results = []
        for register_name in registers:
            field_info = self.query_field_by_name(register_name, field_name)
            if field_info:
                results.append(field_info)

        return results

    def query_by_field_definition(self, field_definition: str) -> dict:
        """
        Query all fields by field definition (RES0, RES1, etc.).
        Returns register_name.field_name[field_position] for each match.

        Args:
            field_definition: Field definition (RES0, RES1, UNPREDICTABLE, UNDEFINED, RAO, UNKNOWN)

        Returns:
            dict with list of matching fields
        """
        # Get all fields with this definition
        result = self.conn.execute("""
            SELECT
                "register_name",
                "field_name",
                "field_position"
            FROM aarch64_sysreg_fields
            WHERE "field_definition" = ?
            ORDER BY "register_name", "field_msb" DESC
        """, [field_definition]).fetchall()

        return {
            'field_definition': field_definition,
            'count': len(result),
            'fields': [
                {
                    'register_name': row[0],
                    'field_name': row[1],
                    'field_position': row[2]
                }
                for row in result
            ]
        }

    def query_registers_by_feature(self, feature_name: str):
        """
        Query register names by architecture feature.

        If feature_name == 'LIST' (case-insensitive), returns a list of all
        feature names registered in the database. Otherwise returns a list of
        register names that belong to the given feature.
        """
        if feature_name is None:
            return []

        if feature_name.strip().upper() == 'LIST':
            rows = self.conn.execute("""
                SELECT DISTINCT feature_name
                FROM aarch64_sysreg
                ORDER BY feature_name
            """).fetchall()
            return [r[0] for r in rows]

        rows = self.conn.execute("""
            SELECT DISTINCT register_name
            FROM aarch64_sysreg
            WHERE feature_name = ?
            ORDER BY register_name
        """, [feature_name]).fetchall()
        return [r[0] for r in rows]

    def format_bit_field_answer(self, info: dict) -> str:
        """Format answer for a bit field query or field name query"""
        output = []
        output.append("=" * 80)
        output.append(f"Register: {info['register_name']}")

        # Show different header based on query type
        if info.get('query_type') == 'field_name':
            output.append(f"Field Name: {info['field_name']}")
        elif info.get('bit_position') is not None:
            output.append(f"Bit Position: [{info['bit_position']}]")

        output.append("=" * 80)
        output.append("")

        # Add register metadata
        output.append(f"Long Name:      {info.get('long_name', 'N/A')}")
        output.append(f"Register Width: {info.get('register_width', 'N/A')} bits")

        # Add features
        if info.get('features'):
            features_str = ', '.join(info['features'])
            output.append(f"Features:       {features_str}")
        output.append("")

        output.append(f"Field Name:     {info['field_name']}")
        output.append(f"Field Position: {info['field_position']}")
        output.append(f"Field Width:    {info['field_width']} bits")

        # Add field definition if available
        if info.get('field_definition'):
            output.append(f"Field Definition: {info['field_definition']}")

        output.append("")

        # Add field description if available
        if info.get('field_description'):
            output.append("Description:")
            # Wrap long description text
            desc = info['field_description']
            if len(desc) > 76:
                words = desc.split()
                line = "  "
                for word in words:
                    if len(line) + len(word) + 1 > 78:
                        output.append(line)
                        line = "  " + word
                    else:
                        line += " " + word if line != "  " else word
                if line != "  ":
                    output.append(line)
            else:
                output.append(f"  {desc}")
            output.append("")

        output.append("Explanation:")
        if info.get('query_type') == 'field_name':
            output.append(f"  The '{info['field_name']}' field is located at bits {info['field_position']},")
            output.append(f"  spanning {info['field_width']} bits total in the {info['register_name']} register.")
        else:
            output.append(f"  Bit {info['bit_position']} belongs to the '{info['field_name']}' field,")
            output.append(f"  which spans bits {info['field_position']} ({info['field_width']} bits total).")
        output.append("")

        return "\n".join(output)

    def format_bit_range_answer(self, info: dict) -> str:
        """Format answer for a bit range query"""
        output = []
        output.append("=" * 80)
        output.append(f"Register: {info['register_name']}")
        output.append(f"Bit Range: {info['bit_range']} ({info['range_width']} bits)")
        output.append("=" * 80)
        output.append("")

        # Add register metadata
        output.append(f"Long Name:      {info.get('long_name', 'N/A')}")
        output.append(f"Register Width: {info.get('register_width', 'N/A')} bits")

        # Add features
        if info.get('features'):
            features_str = ', '.join(info['features'])
            output.append(f"Features:       {features_str}")
        output.append("")

        if len(info['fields']) == 1:
            # Single field
            field = info['fields'][0]
            output.append(f"This range is covered by a single field:")
            output.append(f"  Field Name:     {field['name']}")
            output.append(f"  Field Position: {field['position']}")
            output.append(f"  Field Width:    {field['width']} bits")

            # Add field definition if available
            if field.get('definition'):
                output.append(f"  Field Definition: {field['definition']}")

            # Add description if available
            if field.get('description'):
                output.append("")
                output.append("  Description:")
                desc = field['description']
                if len(desc) > 72:
                    words = desc.split()
                    line = "    "
                    for word in words:
                        if len(line) + len(word) + 1 > 78:
                            output.append(line)
                            line = "    " + word
                        else:
                            line += " " + word if line != "    " else word
                    if line != "    ":
                        output.append(line)
                else:
                    output.append(f"    {desc}")
        else:
            # Multiple fields
            output.append(f"This range spans {len(info['fields'])} field(s):")
            output.append("")

            # Show detailed information for each field
            for i, field in enumerate(info['fields'], 1):
                output.append(f"[{i}] {field['position']:<10} {field['name']:<25} {field['width']:>3} bits")

                # Add field definition if available
                if field.get('definition'):
                    output.append(f"    Field Definition: {field['definition']}")

                if field.get('description'):
                    output.append("    Description:")
                    # Wrap long description text
                    desc = field['description']
                    if len(desc) > 72:
                        words = desc.split()
                        line = "      "
                        for word in words:
                            if len(line) + len(word) + 1 > 78:
                                output.append(line)
                                line = "      " + word
                            else:
                                line += " " + word if line != "      " else word
                        if line != "      ":
                            output.append(line)
                    else:
                        output.append(f"      {desc}")
                # Add spacing between fields for readability
                if i < len(info['fields']):
                    output.append("")

        output.append("")
        return "\n".join(output)

    def format_register_answer(self, info: dict) -> str:
        """Format answer for a register query"""
        output = []
        output.append("=" * 80)
        output.append(f"Register: {info['register_name']}")
        output.append("=" * 80)
        output.append("")
        output.append(f"Long Name:      {info['long_name']}")
        output.append(f"Register Width: {info['register_width']} bits")
        output.append(f"Field Count:    {info['field_count']}")

        # Add features
        if info.get('features'):
            features_str = ', '.join(info['features'])
            output.append(f"Features:       {features_str}")
        output.append("")

        if info['reg_purpose']:
            output.append("Purpose:")
            # Wrap long text
            purpose = info['reg_purpose']
            if len(purpose) > 70:
                # Simple word wrap
                words = purpose.split()
                line = "  "
                for word in words:
                    if len(line) + len(word) + 1 > 78:
                        output.append(line)
                        line = "  " + word
                    else:
                        line += " " + word if line != "  " else word
                if line != "  ":
                    output.append(line)
            else:
                output.append(f"  {purpose}")
            output.append("")

        output.append("Bit Field Layout:")
        output.append("")

        for i, field in enumerate(info['fields'], 1):
            output.append(f"[{i}] {field['position']:<10} {field['name']:<25} {field['width']:>3} bits")

            # Add field definition if available
            if field.get('definition'):
                output.append(f"    Field Definition: {field['definition']}")

            if field.get('description'):
                output.append("    Description:")
                # Wrap long description text
                desc = field['description']
                if len(desc) > 72:
                    words = desc.split()
                    line = "      "
                    for word in words:
                        if len(line) + len(word) + 1 > 78:
                            output.append(line)
                            line = "      " + word
                        else:
                            line += " " + word if line != "      " else word
                    if line != "      ":
                        output.append(line)
                else:
                    output.append(f"      {desc}")
            # Add spacing between fields for readability
            if i < len(info['fields']):
                output.append("")

        output.append("")
        return "\n".join(output)

    def format_field_definition_answer(self, info: dict) -> str:
        """Format answer for a field definition query"""
        output = []

        # Output each field in register_name.field_name[field_position] format
        for field in info['fields']:
            output.append(f"{field['register_name']}.{field['field_name']}{field['field_position']}")

        return "\n".join(output)

    def format_multiple_fields_answer(self, field_infos: list) -> str:
        """Format answer for field-name-only query (multiple registers)"""
        if not field_infos:
            return ""

        output = []

        # Show summary header
        field_name = field_infos[0]['field_name']
        output.append("=" * 80)
        output.append(f"Field Name: {field_name}")
        output.append(f"Found in {len(field_infos)} register(s)")
        output.append("=" * 80)
        output.append("")

        # Show each register's field info
        for i, info in enumerate(field_infos, 1):
            if i > 1:
                output.append("")
                output.append("-" * 80)
                output.append("")

            output.append(f"[{i}] Register: {info['register_name']}")
            output.append(f"    Long Name:      {info.get('long_name', 'N/A')}")
            output.append(f"    Register Width: {info.get('register_width', 'N/A')} bits")

            # Add features
            if info.get('features'):
                features_str = ', '.join(info['features'])
                output.append(f"    Features:       {features_str}")

            output.append("")
            output.append(f"    Field Position: {info['field_position']}")
            output.append(f"    Field Width:    {info['field_width']} bits")

            # Add field definition if available
            if info.get('field_definition'):
                output.append(f"    Field Definition: {info['field_definition']}")

            # Add field description if available
            if info.get('field_description'):
                output.append("")
                output.append("    Description:")
                desc = info['field_description']
                if len(desc) > 72:
                    words = desc.split()
                    line = "      "
                    for word in words:
                        if len(line) + len(word) + 1 > 78:
                            output.append(line)
                            line = "      " + word
                        else:
                            line += " " + word if line != "      " else word
                    if line != "      ":
                        output.append(line)
                else:
                    output.append(f"      {desc}")

        output.append("")
        return "\n".join(output)

    def answer_query(self, query: str) -> str:
        """Main method to answer a user query"""
        parsed = self.parse_query(query)

        if not parsed:
            return (
                f"Error: Invalid query format: '{query}'\n\n"
                "Supported formats:\n"
                "  - REGISTER_NAME[bit]          (e.g., HCR_EL2[1])\n"
                "  - REGISTER_NAME[high:low]     (e.g., HCR_EL2[31:8])\n"
                "  - REGISTER_NAME.FIELD         (e.g., HCR_EL2.TGE)\n"
                "  - REGISTER_NAME.FIELD[range]  (e.g., TRCIDR12.NUMCONDKEY[31:0])\n"
                "  - REGISTER_NAME               (e.g., ALLINT)\n"
                "  - FIELD_NAME                  (e.g., NUMCONDKEY)\n"
                "  - FIELD_DEFINITION            (e.g., RES0, RES1, UNPREDICTABLE)\n"
            )

        # Handle field definition query
        field_definition = parsed.get('field_definition')
        if field_definition is not None:
            info = self.query_by_field_definition(field_definition)
            return self.format_field_definition_answer(info)

        register_name = parsed['register']
        bit_start = parsed['bit_start']
        bit_end = parsed['bit_end']
        field_name = parsed.get('field_name')
        verify_field = parsed.get('verify_field')
        field_only = parsed.get('field_only', False)

        # Handle field-name-only query (search across all registers)
        if field_only and field_name is not None:
            field_infos = self.query_all_fields_by_name(field_name)
            if field_infos:
                return self.format_multiple_fields_answer(field_infos)
            else:
                return (
                    f"Error: Field '{field_name}' not found in any register\n"
                    f"The field name may not exist in the database.\n"
                )

        # Handle field name query with register
        if field_name is not None and register_name is not None:
            info = self.query_field_by_name(register_name, field_name)
            if info:
                return self.format_bit_field_answer(info)
            else:
                return (
                    f"Error: Field '{field_name}' not found in register '{register_name}'\n"
                    f"The register or field may not exist.\n"
                )

        # Handle bit position/range queries
        if bit_start is not None:
            # First, verify field name if provided (REGISTER.FIELD[range] format)
            if verify_field is not None:
                # Check if the specified field exists and matches the bit range
                # Pass bit_start and bit_end to find the exact field at this position
                field_info = self.query_field_by_name(register_name, verify_field, bit_start, bit_end)
                if not field_info:
                    # Field with this name at this bit range doesn't exist
                    # Check if field exists at any position
                    any_field = self.query_field_by_name(register_name, verify_field)
                    if any_field:
                        return (
                            f"Error: Field '{verify_field}' exists but not at bit range [{bit_end}:{bit_start}]\n"
                            f"Actual position of '{verify_field}': {any_field['field_position']}\n"
                            f"Processing query as: {register_name}[{bit_end}:{bit_start}]\n"
                        )
                    else:
                        return (
                            f"Error: Field '{verify_field}' not found in register '{register_name}'\n"
                            f"The field '{verify_field}[{bit_end}:{bit_start}]' does not exist.\n"
                        )
                # Field name and bit range match, proceed with the query

            if bit_start == bit_end:
                # Query specific bit field (single bit)
                info = self.query_bit_field(register_name, bit_start)
                if info:
                    return self.format_bit_field_answer(info)
                else:
                    return (
                        f"Error: No field found for bit [{bit_start}] in register '{register_name}'\n"
                        f"The register may not exist or the bit position may be invalid.\n"
                    )
            else:
                # Query bit range (multiple bits)
                info = self.query_bit_range(register_name, bit_start, bit_end)
                if info:
                    return self.format_bit_range_answer(info)
                else:
                    return (
                        f"Error: No fields found for bit range [{bit_end}:{bit_start}] in register '{register_name}'\n"
                        f"The register may not exist or the bit range may be invalid.\n"
                    )
        else:
            # Query entire register
            info = self.query_register(register_name)
            if info:
                return self.format_register_answer(info)
            else:
                return f"Error: Register '{register_name}' not found in database.\n"

    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Query AArch64 system registers and fields")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--reg', '-r', metavar='REG', help="Register query. Accepts formats like 'HCR_EL2[1]', 'HCR_EL2[31:8]', 'HCR_EL2.TGE', or 'HCR_EL2'")
    group.add_argument('--name', '-n', metavar='FIELD_NAME', help="Search for registers containing the given field name")
    group.add_argument('--fielddef', '-f', metavar='FIELD_DEF', help="Search for fields by definition. One of: RES0, RES1, UNPREDICTABLE, UNDEFINED, RAO, UNKNOWN")
    group.add_argument('--feat', '-F', metavar='FEAT_NAME', help="Search for registers by feature name, or use 'LIST' to list all features in the DB")

    parser.add_argument('--json', action='store_true', help='Output results in JSON format')

    args = parser.parse_args()

    try:
        agent = RegisterQueryAgent(DB_FILE)

        # Handle --reg
        if args.reg:
            parsed = agent.parse_query(args.reg)
            if not parsed:
                print(f"Error: Invalid query format: '{args.reg}'")
                sys.exit(1)

            # If parse_query returned a field_definition (e.g., RES0), handle it
            if parsed.get('field_definition') is not None:
                info = agent.query_by_field_definition(parsed['field_definition'])
                if args.json:
                    print(json.dumps(info, indent=2))
                else:
                    print(agent.format_field_definition_answer(info))
                agent.close()
                return

            register_name = parsed['register']
            bit_start = parsed['bit_start']
            bit_end = parsed['bit_end']
            field_name = parsed.get('field_name')
            verify_field = parsed.get('verify_field')
            field_only = parsed.get('field_only', False)

            # Field-name-only across registers
            if field_only and field_name is not None:
                field_infos = agent.query_all_fields_by_name(field_name)
                if args.json:
                    print(json.dumps(field_infos, indent=2))
                else:
                    print(agent.format_multiple_fields_answer(field_infos))
                agent.close()
                return

            # Field name with register (e.g., REG.FIELD)
            if field_name is not None and register_name is not None:
                info = agent.query_field_by_name(register_name, field_name)
                if args.json:
                    print(json.dumps(info if info else {}, indent=2))
                else:
                    if info:
                        print(agent.format_bit_field_answer(info))
                    else:
                        print(f"Error: Field '{field_name}' not found in register '{register_name}'")
                agent.close()
                return

            # Bit position / range
            if bit_start is not None:
                # Verify field if requested
                if verify_field is not None:
                    field_info = agent.query_field_by_name(register_name, verify_field, bit_start, bit_end)
                    if not field_info:
                        any_field = agent.query_field_by_name(register_name, verify_field)
                        if any_field:
                            msg = {
                                'error': 'field_mismatch',
                                'message': f"Field '{verify_field}' exists but not at bit range [{bit_end}:{bit_start}]",
                                'actual_position': any_field['field_position'],
                                'treat_as': f"{register_name}[{bit_end}:{bit_start}]"
                            }
                            if args.json:
                                print(json.dumps(msg, indent=2))
                            else:
                                print(msg['message'])
                                print(f"Actual position of '{verify_field}': {any_field['field_position']}")
                                print(f"Processing query as: {register_name}[{bit_end}:{bit_start}]")
                            agent.close()
                            return
                        else:
                            err = f"Error: Field '{verify_field}' not found in register '{register_name}'"
                            if args.json:
                                print(json.dumps({'error': 'field_not_found', 'message': err}, indent=2))
                            else:
                                print(err)
                            agent.close()
                            return

                if bit_start == bit_end:
                    info = agent.query_bit_field(register_name, bit_start)
                    if args.json:
                        print(json.dumps(info if info else {}, indent=2))
                    else:
                        if info:
                            print(agent.format_bit_field_answer(info))
                        else:
                            print(f"Error: No field found for bit [{bit_start}] in register '{register_name}'")
                    agent.close()
                    return
                else:
                    info = agent.query_bit_range(register_name, bit_start, bit_end)
                    if args.json:
                        print(json.dumps(info if info else {}, indent=2))
                    else:
                        if info:
                            print(agent.format_bit_range_answer(info))
                        else:
                            print(f"Error: No fields found for bit range [{bit_end}:{bit_start}] in register '{register_name}'")
                    agent.close()
                    return

            # Entire register
            info = agent.query_register(register_name)
            if args.json:
                print(json.dumps(info if info else {}, indent=2))
            else:
                if info:
                    print(agent.format_register_answer(info))
                else:
                    print(f"Error: Register '{register_name}' not found in database.")
            agent.close()
            return

        # Handle --name (search field across registers)
        if args.name:
            field_infos = agent.query_all_fields_by_name(args.name)
            if args.json:
                print(json.dumps(field_infos, indent=2))
            else:
                print(agent.format_multiple_fields_answer(field_infos))
            agent.close()
            return

        # Handle --feat (feature -> register list or LIST -> feature list)
        if args.feat:
            feat_val = args.feat.strip()
            results = agent.query_registers_by_feature(feat_val)
            if args.json:
                print(json.dumps(results, indent=2))
            else:
                if results:
                    print("\n".join(results))
                else:
                    if feat_val.upper() == 'LIST':
                        print("No features found in database.")
                    else:
                        print(f"No registers found for feature '{feat_val}'")
            agent.close()
            return

        # Handle --fielddef
        if args.fielddef:
            # Be tolerant of accidental merging of tokens (e.g. non-ASCII space causing
            # "RES0　--json" to be passed as a single argument). Extract the first token
            # as the field definition, and enable JSON output if `--json` appears inside.
            raw_fd = args.fielddef
            if '--json' in raw_fd:
                args.json = True
                raw_fd = raw_fd.replace('--json', ' ')

            # Split on any whitespace (including Unicode spaces) and take the first token
            parts = re.split(r"\s+", raw_fd.strip())
            fd = parts[0] if parts and parts[0] else ''

            allowed = {'RES0', 'RES1', 'UNPREDICTABLE', 'UNDEFINED', 'RAO', 'UNKNOWN'}
            if fd not in allowed:
                print(f"Error: --fielddef must be one of: {', '.join(sorted(allowed))}")
                agent.close()
                sys.exit(1)

            info = agent.query_by_field_definition(fd)
            if args.json:
                print(json.dumps(info, indent=2))
            else:
                print(agent.format_field_definition_answer(info))
            agent.close()
            return

    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
