#!/usr/bin/env python3
"""
AArch64 System Register Query Agent

This script answers questions about AArch64 system registers and their bit fields.

Examples:
    python3 query_register.py "HCR_EL2[1]"
    python3 query_register.py "ALLINT[13]"
    python3 query_register.py "ACCDATA_EL1"
"""

import sys
import re
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
        Parse user query to extract register name and optional bit position/range.

        Examples:
            "HCR_EL2[1]" -> {'register': 'HCR_EL2', 'bit_start': 1, 'bit_end': 1}
            "HCR_EL2[31:8]" -> {'register': 'HCR_EL2', 'bit_start': 8, 'bit_end': 31}
            "ACCDATA_EL1" -> {'register': 'ACCDATA_EL1', 'bit_start': None, 'bit_end': None}
        """
        # Pattern: REGISTER_NAME[bit_position] or REGISTER_NAME[bit_high:bit_low]
        pattern = r'^([A-Z0-9_<>]+)(?:\[(\d+)(?::(\d+))?\])?$'
        match = re.match(pattern, query.strip())

        if not match:
            return None

        register_name = match.group(1)

        if match.group(2):
            if match.group(3):
                # Range format: [high:low]
                bit_high = int(match.group(2))
                bit_low = int(match.group(3))
                # Ensure high >= low
                bit_start = min(bit_high, bit_low)
                bit_end = max(bit_high, bit_low)
            else:
                # Single bit format: [bit]
                bit_start = int(match.group(2))
                bit_end = bit_start
        else:
            # No bit specification
            bit_start = None
            bit_end = None

        return {
            'register': register_name,
            'bit_start': bit_start,
            'bit_end': bit_end
        }

    def query_bit_field(self, register_name: str, bit_position: int) -> dict:
        """
        Query information about a specific bit position in a register.

        Returns:
            dict with field information, or None if not found
        """
        # Find the field that contains this bit position
        result = self.conn.execute("""
            SELECT
                "register_name",
                "field_name",
                "field_msb",
                "field_lsb",
                "field_width",
                "field_position",
                "field_description"
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
            'field_name': field[1],
            'field_msb': field[2],
            'field_lsb': field[3],
            'field_width': field[4],
            'field_position': field[5],
            'field_description': field[6],
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
                "field_description"
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
                'description': f[6]
            }
            for f in result
        ]

        return {
            'register_name': register_name,
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
        # Get register info
        reg_info = self.conn.execute("""
            SELECT DISTINCT
                register_name,
                long_name,
                register_width,
                field_count,
                reg_purpose
            FROM aarch64_sysreg
            WHERE register_name = ?
            LIMIT 1
        """, [register_name]).fetchone()

        if not reg_info:
            return None

        # Get all fields
        fields = self.conn.execute("""
            SELECT
                "field_name",
                "field_msb",
                "field_lsb",
                "field_width",
                "field_position",
                "field_description"
            FROM aarch64_sysreg_fields
            WHERE "register_name" = ?
            ORDER BY "field_msb" DESC
        """, [register_name]).fetchall()

        return {
            'register_name': reg_info[0],
            'long_name': reg_info[1],
            'register_width': reg_info[2],
            'field_count': reg_info[3],
            'reg_purpose': reg_info[4],
            'fields': [
                {
                    'name': f[0],
                    'msb': f[1],
                    'lsb': f[2],
                    'width': f[3],
                    'position': f[4],
                    'description': f[5]
                }
                for f in fields
            ]
        }

    def format_bit_field_answer(self, info: dict) -> str:
        """Format answer for a bit field query"""
        output = []
        output.append("=" * 80)
        output.append(f"Register: {info['register_name']}")
        output.append(f"Bit Position: [{info['bit_position']}]")
        output.append("=" * 80)
        output.append("")
        output.append(f"Field Name:     {info['field_name']}")
        output.append(f"Field Position: {info['field_position']}")
        output.append(f"Field Width:    {info['field_width']} bits")
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

        if len(info['fields']) == 1:
            # Single field
            field = info['fields'][0]
            output.append(f"This range is covered by a single field:")
            output.append(f"  Field Name:     {field['name']}")
            output.append(f"  Field Position: {field['position']}")
            output.append(f"  Field Width:    {field['width']} bits")

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

    def answer_query(self, query: str) -> str:
        """Main method to answer a user query"""
        parsed = self.parse_query(query)

        if not parsed:
            return (
                f"Error: Invalid query format: '{query}'\n\n"
                "Supported formats:\n"
                "  - REGISTER_NAME[bit]       (e.g., HCR_EL2[1])\n"
                "  - REGISTER_NAME[high:low]  (e.g., HCR_EL2[31:8])\n"
                "  - REGISTER_NAME            (e.g., ALLINT)\n"
            )

        register_name = parsed['register']
        bit_start = parsed['bit_start']
        bit_end = parsed['bit_end']

        if bit_start is not None:
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
    if len(sys.argv) < 2:
        print("Usage: python3 query_register.py <query>")
        print()
        print("Examples:")
        print("  python3 query_register.py 'HCR_EL2[1]'       # Single bit")
        print("  python3 query_register.py 'HCR_EL2[31:8]'    # Bit range")
        print("  python3 query_register.py 'ALLINT[13]'       # Single bit")
        print("  python3 query_register.py 'ACCDATA_EL1'      # Entire register")
        print()
        sys.exit(1)

    query = sys.argv[1]

    try:
        agent = RegisterQueryAgent(DB_FILE)
        answer = agent.answer_query(query)
        print(answer)
        agent.close()
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
