#!/usr/bin/env python3
"""
AArch64 ISA Database Query Tool

This script provides a command-line interface to query the AArch64 ISA database
for instruction encodings, mnemonics, and operands.

Usage:
    query_isa.py --n <MNEMONIC>              # Show encoding pattern(s) for mnemonic
    query_isa.py --op <OPCODE>               # Decode opcode to mnemonic + operands
    query_isa.py --hint <PARTIAL_OPCODE>     # Find matching mnemonics for partial opcode
    query_isa.py --help                      # Show this help message

Examples:
    query_isa.py --n ADD
    query_isa.py --op 0x11000000
    query_isa.py --op 0x91_00_00_00                              # With separators
    query_isa.py --op 0b10010001_00000000_00000000_00000000
    query_isa.py --hint 0x1100XXXX                               # X = 4 don't care bits
    query_isa.py --hint 0x91_00_XX_XX                            # Separators + don't care
    query_isa.py --hint 0x9x00xxxx                               # x = 4 don't care bits
    query_isa.py --hint 0b1001xxxx_0000xxxx_xxxxxxxx_xxxxxxxx    # x = 1 don't care bit

Note on separator characters (optional):
    - '_' or ':' can be used as 8-bit separators for readability
    - Examples: 0x91_00_00_00, 0x91:00:00:00
    - Works with both hex and binary formats, and with don't care notation

Note on don't care notation:
    - Hex format: Both 'X' and 'x' represent 4 binary don't care bits
    - Binary format: Both 'X' and 'x' represent 1 binary don't care bit
    - Mixed usage is allowed (e.g., 0x9X0x, 0x91_00_Xx_XX)
"""

import sys
import argparse
import duckdb
import os

DB_FILENAME = 'aarch64_isa_db.duckdb'

def connect_db():
    """Connect to the ISA database."""
    if not os.path.exists(DB_FILENAME):
        print(f"Error: Database file '{DB_FILENAME}' not found.")
        print(f"Please generate the database first using: python gen_aarch64_isa_db.py")
        sys.exit(1)
    return duckdb.connect(DB_FILENAME)

def parse_opcode(opcode_str):
    """
    Parse opcode string to 32-bit binary string.
    Supports formats: 0xHEXVALUE, 0bBINARYVALUE
    Returns: string of '0', '1', or 'X' (for don't care in partial match)

    For hex format: 'X' represents 4 don't care bits (e.g., 0x9X0 -> 1001XXXX0000)
    For binary format: 'x' represents 1 don't care bit (e.g., 0b1001x -> 1001X)
    Mixed format allowed: 0x9x0 where lowercase 'x' in hex means 4 binary 'x' bits

    Separator support: '_' or ':' can be used as 8-bit separators (ignored during parsing)
    Examples:
        0x91_00_00_00 or 0x91:00:00:00
        0b10010001_00000000_00000000_00000000
    """
    opcode_str = opcode_str.strip()

    # Remove separator characters ('_' and ':') - they are only for readability
    opcode_str = opcode_str.replace('_', '').replace(':', '')

    # Handle hex format (0x...)
    if opcode_str.startswith('0x') or opcode_str.startswith('0X'):
        hex_str = opcode_str[2:]
        # Check for 'X' or 'x' in hex (for partial matching)
        if 'X' in hex_str or 'x' in hex_str:
            # Convert hex to binary, handling both X and x
            binary = ''
            for c in hex_str:
                if c == 'X':
                    # Uppercase X in hex = 4 don't care bits
                    binary += 'XXXX'
                elif c == 'x':
                    # Lowercase x in hex = 4 individual don't care bits (xxxx)
                    binary += 'xxxx'
                elif c.upper() in '0123456789ABCDEF':
                    binary += format(int(c, 16), '04b')
                else:
                    raise ValueError(f"Invalid hex character: {c}")
        else:
            # Pure hex value
            try:
                value = int(hex_str, 16)
                binary = format(value, '032b')
            except ValueError:
                raise ValueError(f"Invalid hex value: {hex_str}")

    # Handle binary format (0b...)
    elif opcode_str.startswith('0b') or opcode_str.startswith('0B'):
        binary = opcode_str[2:]
        # Validate binary string (should contain only 0, 1, x, X)
        for c in binary:
            if c not in '01xX':
                raise ValueError(f"Invalid binary character: {c}")
        # Keep case: X and x both mean don't care in binary format

    else:
        raise ValueError(f"Opcode must start with 0x (hex) or 0b (binary)")

    # Normalize: convert all x and X to uppercase X for don't care
    binary = binary.replace('x', 'X')

    # Pad or truncate to 32 bits
    if len(binary) < 32:
        # Pad with leading zeros (not X)
        binary = binary.zfill(32)
    elif len(binary) > 32:
        raise ValueError(f"Opcode too long: {len(binary)} bits (expected 32)")

    return binary

def binary_to_hex(binary_str):
    """Convert 32-bit binary string to hex string (handling X for don't care)."""
    if 'X' in binary_str:
        # Replace X with 0 for display purposes
        display_bin = binary_str.replace('X', '0')
        value = int(display_bin, 2)
        return f"0x{value:08x} (with X=don't care)"
    else:
        value = int(binary_str, 2)
        return f"0x{value:08x}"

def query_by_mnemonic(conn, mnemonic):
    """
    Query encodings for a given mnemonic.
    --n option implementation
    """
    mnemonic = mnemonic.upper()

    # Query all encodings for this mnemonic
    bit_cols = ", ".join([f"e.bit_{i}" for i in range(31, -1, -1)])
    query = f"""
        SELECT
            i.mnemonic,
            i.title,
            i.feature_name,
            e.encoding_name,
            e.encoding_label,
            e.asm_template,
            {bit_cols}
        FROM aarch64_isa_instructions i
        JOIN aarch64_isa_encodings e ON i.id = e.instruction_id
        WHERE UPPER(i.mnemonic) = ?
        ORDER BY e.encoding_name
    """

    results = conn.execute(query, [mnemonic]).fetchall()

    if not results:
        print(f"No instruction found with mnemonic: {mnemonic}")
        return

    print("=" * 80)
    print(f"Mnemonic: {results[0][0]}")
    print(f"Title: {results[0][1]}")
    print(f"Features: {results[0][2]}")
    print("=" * 80)
    print()

    for idx, row in enumerate(results, 1):
        encoding_name = row[3]
        encoding_label = row[4]
        asm_template = row[5]
        bits = [row[6 + i] for i in range(32)]

        # Build binary pattern string
        binary_pattern = ""
        fixed_bits = ""
        for b in bits:
            if b in ('0', '1'):
                binary_pattern += b
                fixed_bits += b
            else:
                binary_pattern += 'X'
                fixed_bits += '0'  # For hex display

        print(f"[{idx}] Encoding: {encoding_name}")
        if encoding_label:
            print(f"    Label: {encoding_label}")
        print(f"    Assembly: {asm_template}")
        print(f"    Binary Pattern:  {' '.join([binary_pattern[i:i+4] for i in range(0, 32, 4)])}")
        print(f"    Hex Pattern:     {binary_to_hex(binary_pattern)}")

        # Show bit field layout
        print(f"    Bit Fields:")
        current_field = None
        field_start = 31
        for i, b in enumerate(bits):
            bit_pos = 31 - i
            if b != current_field:
                if current_field is not None:
                    field_end = bit_pos + 1
                    if current_field in ('0', '1'):
                        print(f"      [{field_start}:{field_end}] = {current_field} (fixed)")
                    else:
                        print(f"      [{field_start}:{field_end}] = {current_field} (variable)")
                current_field = b
                field_start = bit_pos
        # Last field
        if current_field is not None:
            if current_field in ('0', '1'):
                print(f"      [{field_start}:0] = {current_field} (fixed)")
            else:
                print(f"      [{field_start}:0] = {current_field} (variable)")

        print()

def query_by_opcode(conn, opcode_str):
    """
    Decode opcode to mnemonic and operands.
    --op option implementation
    """
    try:
        binary = parse_opcode(opcode_str)
    except ValueError as e:
        print(f"Error parsing opcode: {e}")
        return

    # Query all encodings and match against the binary
    bit_cols = ", ".join([f"e.bit_{i}" for i in range(31, -1, -1)])
    query = f"""
        SELECT
            i.mnemonic,
            i.title,
            i.feature_name,
            e.encoding_name,
            e.encoding_label,
            e.asm_template,
            {bit_cols}
        FROM aarch64_isa_instructions i
        JOIN aarch64_isa_encodings e ON i.id = e.instruction_id
    """

    results = conn.execute(query).fetchall()

    matches = []
    for row in results:
        mnemonic = row[0]
        title = row[1]
        feature_name = row[2]
        encoding_name = row[3]
        encoding_label = row[4]
        asm_template = row[5]
        bits = [row[6 + i] for i in range(32)]

        # Check if opcode matches this encoding
        match = True
        operands = {}
        for i, pattern_bit in enumerate(bits):
            opcode_bit = binary[i]
            if pattern_bit in ('0', '1'):
                # Fixed bit must match
                if opcode_bit != pattern_bit:
                    match = False
                    break
            else:
                # Variable field - extract value
                if pattern_bit not in operands:
                    operands[pattern_bit] = []
                operands[pattern_bit].append(opcode_bit)

        if match:
            matches.append({
                'mnemonic': mnemonic,
                'title': title,
                'feature_name': feature_name,
                'encoding_name': encoding_name,
                'encoding_label': encoding_label,
                'asm_template': asm_template,
                'operands': operands
            })

    if not matches:
        print(f"No matching instruction found for opcode: {opcode_str}")
        print(f"Binary: {' '.join([binary[i:i+4] for i in range(0, 32, 4)])}")
        print(f"Hex: {binary_to_hex(binary)}")
        return

    # For each match, construct the actual ARM assembly instruction
    for match in matches:
        asm_template = match['asm_template']
        operands = match['operands']

        # Build the assembly instruction by replacing placeholders with actual values
        assembly = asm_template

        # Collect immediate values by type
        imm_values = {}
        reg_values = {}
        shift_value = None
        crm_value = None
        op2_value = None

        for field, bits in operands.items():
            bit_str = ''.join(bits)
            value = int(bit_str, 2)

            if field == 'Rd':
                reg_values['Rd'] = value
            elif field == 'Rn':
                reg_values['Rn'] = value
            elif field == 'Rm':
                reg_values['Rm'] = value
            elif field.startswith('imm'):
                # Map imm12 -> imm, imm8 -> imm, etc.
                imm_values['imm'] = value
            elif field.startswith('off'):
                imm_values['offs'] = value
            elif field == 'sh':
                shift_value = value
            elif field == 'CRm':
                crm_value = value
            elif field == 'op2':
                op2_value = value

        # For HINT instruction, combine CRm and op2 to form the immediate value
        # HINT #imm where imm = (CRm << 3) | op2
        if crm_value is not None and op2_value is not None and 'imm' not in imm_values:
            imm_values['imm'] = (crm_value << 3) | op2_value

        # Replace register operands
        if 'Rd' in reg_values:
            rd = reg_values['Rd']
            if '<Xd|SP>' in assembly:
                assembly = assembly.replace('<Xd|SP>', f'x{rd}' if rd != 31 else 'sp')
            elif '<Xd>' in assembly:
                assembly = assembly.replace('<Xd>', f'x{rd}')
            elif '<Wd|WSP>' in assembly:
                assembly = assembly.replace('<Wd|WSP>', f'w{rd}' if rd != 31 else 'wsp')
            elif '<Wd>' in assembly:
                assembly = assembly.replace('<Wd>', f'w{rd}')

        if 'Rn' in reg_values:
            rn = reg_values['Rn']
            if '<Xn|SP>' in assembly:
                assembly = assembly.replace('<Xn|SP>', f'x{rn}' if rn != 31 else 'sp')
            elif '<Xn>' in assembly:
                assembly = assembly.replace('<Xn>', f'x{rn}')
            elif '<Wn|WSP>' in assembly:
                assembly = assembly.replace('<Wn|WSP>', f'w{rn}' if rn != 31 else 'wsp')
            elif '<Wn>' in assembly:
                assembly = assembly.replace('<Wn>', f'w{rn}')

        if 'Rm' in reg_values:
            rm = reg_values['Rm']
            if '<Xm>' in assembly or '<R><m>' in assembly:
                assembly = assembly.replace('<Xm>', f'x{rm}')
                assembly = assembly.replace('<R><m>', f'x{rm}')
            elif '<Wm>' in assembly:
                assembly = assembly.replace('<Wm>', f'w{rm}')

        # Replace immediate values (always use hex format)
        if 'imm' in imm_values:
            imm_hex = f'#0x{imm_values["imm"]:x}'
            assembly = assembly.replace('#<imm>', imm_hex)
            assembly = assembly.replace('<imm>', f'0x{imm_values["imm"]:x}')

        if 'offs' in imm_values:
            assembly = assembly.replace('<offs>', f'0x{imm_values["offs"]:x}')

        # Handle shift field
        if shift_value is not None:
            if shift_value == 0:
                # Remove shift part if shift is 0
                assembly = assembly.replace('{, <shift>}', '')
            else:
                assembly = assembly.replace('<shift>', 'lsl #12')
                assembly = assembly.replace('{, ', ', ').replace('}', '')

        # Clean up any remaining optional parts with default values
        assembly = assembly.replace('{, <shift>}', '')
        assembly = assembly.replace('{, <extend> {#<amount>}}', '')
        assembly = assembly.replace('{, <shift> #<amount>}', '')

        # Clean up extra spaces
        assembly = ' '.join(assembly.split())

        print(assembly)

def query_by_hint(conn, partial_opcode_str):
    """
    Find matching mnemonics for partial opcode (with X for don't care).
    --hint option implementation
    """
    try:
        binary = parse_opcode(partial_opcode_str)
    except ValueError as e:
        print(f"Error parsing partial opcode: {e}")
        return

    # Query all encodings and match against the partial binary
    bit_cols = ", ".join([f"e.bit_{i}" for i in range(31, -1, -1)])
    query = f"""
        SELECT
            i.mnemonic,
            i.title,
            i.feature_name,
            e.encoding_name,
            e.encoding_label,
            e.asm_template,
            {bit_cols}
        FROM aarch64_isa_instructions i
        JOIN aarch64_isa_encodings e ON i.id = e.instruction_id
    """

    results = conn.execute(query).fetchall()

    matches = []
    for row in results:
        mnemonic = row[0]
        title = row[1]
        feature_name = row[2]
        encoding_name = row[3]
        encoding_label = row[4]
        asm_template = row[5]
        bits = [row[6 + i] for i in range(32)]

        # Check if partial opcode matches this encoding
        match = True
        for i, pattern_bit in enumerate(bits):
            partial_bit = binary[i]
            if partial_bit == 'X':
                # Don't care - always matches
                continue
            if pattern_bit in ('0', '1'):
                # Fixed bit must match
                if partial_bit != pattern_bit:
                    match = False
                    break
            # Variable field always matches non-X partial bits

        if match:
            matches.append({
                'mnemonic': mnemonic,
                'title': title,
                'feature_name': feature_name,
                'encoding_name': encoding_name,
                'encoding_label': encoding_label,
                'asm_template': asm_template,
                'pattern': ''.join([b if b in ('0', '1') else 'X' for b in bits])
            })

    if not matches:
        print(f"No matching instruction found for partial opcode: {partial_opcode_str}")
        print(f"Binary: {' '.join([binary[i:i+4] for i in range(0, 32, 4)])}")
        return

    # Output only ARM Assembler templates (one per line)
    for match in matches:
        print(match['asm_template'])

def main():
    parser = argparse.ArgumentParser(
        description='AArch64 ISA Database Query Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --n ADD
  %(prog)s --op 0x11000000
  %(prog)s --op 0x91_00_00_00                      # Separator supported ('_' or ':')
  %(prog)s --op 0b10010001_00000000_00000000_00000000
  %(prog)s --hint 0x1100XXXX                       # X in hex = 4 don't care bits
  %(prog)s --hint 0x91_00_XX_XX                    # Separators work with don't care
  %(prog)s --hint 0x9x00xxxx                       # x in hex = 4 don't care bits
  %(prog)s --hint 0b1001xxxx_0000xxxx_xxxxxxxx_xxxxxxxx

Separator characters (optional, for readability):
  '_' or ':' can be used as 8-bit separators in hex and binary formats
  Examples: 0x91_00_00_00, 0x91:00:00:00, 0b10010001_00000000_00000000_00000000

Don't care notation:
  Hex format:    'X' or 'x' = 4 binary don't care bits
  Binary format: 'X' or 'x' = 1 binary don't care bit
  Mixed usage allowed (e.g., 0x9X0x, 0x91_00_Xx_XX)
        """
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--n', metavar='MNEMONIC',
                      help='Show encoding pattern(s) for mnemonic')
    group.add_argument('--op', metavar='OPCODE',
                      help='Decode opcode to mnemonic + operands (format: 0xHEX or 0bBINARY)')
    group.add_argument('--hint', metavar='PARTIAL_OPCODE',
                      help='Find matching mnemonics for partial opcode (use X/x for don\'t care)')

    args = parser.parse_args()

    conn = connect_db()

    try:
        if args.n:
            query_by_mnemonic(conn, args.n)
        elif args.op:
            query_by_opcode(conn, args.op)
        elif args.hint:
            query_by_hint(conn, args.hint)
    finally:
        conn.close()

if __name__ == '__main__':
    main()
