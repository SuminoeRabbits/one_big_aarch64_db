#!/usr/bin/env python3
"""
Generate C++ encoding data from aarch64_isa_db.duckdb
Split into multiple source files for parallel compilation
"""
import duckdb
import sys
import os

NUM_SPLIT_FILES = 10  # Split into 10 files for parallel compilation

def main():
    conn = duckdb.connect('../aarch64_isa_db.duckdb')

    # Get all encodings with their bit patterns
    query = '''
        SELECT e.asm_template,
               e.bit_31, e.bit_30, e.bit_29, e.bit_28, e.bit_27, e.bit_26, e.bit_25, e.bit_24,
               e.bit_23, e.bit_22, e.bit_21, e.bit_20, e.bit_19, e.bit_18, e.bit_17, e.bit_16,
               e.bit_15, e.bit_14, e.bit_13, e.bit_12, e.bit_11, e.bit_10, e.bit_9, e.bit_8,
               e.bit_7, e.bit_6, e.bit_5, e.bit_4, e.bit_3, e.bit_2, e.bit_1, e.bit_0
        FROM aarch64_isa_encodings e
        ORDER BY e.id
    '''

    results = conn.execute(query).fetchall()
    conn.close()

    total_encodings = len(results)
    encodings_per_file = (total_encodings + NUM_SPLIT_FILES - 1) // NUM_SPLIT_FILES

    # Generate header file with structure definition
    with open('encoding_data.h', 'w') as f:
        f.write(f"// Auto-generated encoding data ({total_encodings} encodings)\n")
        f.write("#ifndef ENCODING_DATA_H\n")
        f.write("#define ENCODING_DATA_H\n\n")
        f.write("#include <cstdint>\n")
        f.write("#include <string>\n\n")
        f.write("struct EncodingPattern {\n")
        f.write("    std::string asm_template;\n")
        f.write("    uint32_t fixed_bits;      // Bits that must match (0 or 1)\n")
        f.write("    uint32_t fixed_mask;      // Mask for fixed bits\n")
        f.write("    std::string bit_fields[32]; // Field names for variable bits (MSB first)\n")
        f.write("};\n\n")

        # Declare extern arrays
        for i in range(NUM_SPLIT_FILES):
            f.write(f"extern const EncodingPattern ENCODINGS_{i}[];\n")
            f.write(f"extern const size_t NUM_ENCODINGS_{i};\n")

        f.write(f"\nstatic const size_t TOTAL_ENCODINGS = {total_encodings};\n")
        f.write(f"static const size_t NUM_ENCODING_ARRAYS = {NUM_SPLIT_FILES};\n\n")
        f.write("#endif // ENCODING_DATA_H\n")

    # Generate split source files
    for file_idx in range(NUM_SPLIT_FILES):
        start_idx = file_idx * encodings_per_file
        end_idx = min(start_idx + encodings_per_file, total_encodings)

        with open(f'encoding_data_{file_idx}.cpp', 'w') as f:
            f.write(f"// Auto-generated encoding data part {file_idx + 1}/{NUM_SPLIT_FILES}\n")
            f.write("#include \"encoding_data.h\"\n\n")
            f.write(f"const EncodingPattern ENCODINGS_{file_idx}[] = {{\n")

            for row in results[start_idx:end_idx]:
                asm_template = row[0]
                bits = row[1:33]  # bit_31 to bit_0

                # Calculate fixed bits and mask
                fixed_bits = 0
                fixed_mask = 0

                for i, bit in enumerate(bits):
                    bit_pos = 31 - i  # MSB first
                    if bit == '0':
                        fixed_mask |= (1 << bit_pos)
                    elif bit == '1':
                        fixed_mask |= (1 << bit_pos)
                        fixed_bits |= (1 << bit_pos)

                # Escape the template string
                escaped_template = asm_template.replace('\\', '\\\\').replace('"', '\\"')

                # Build bit fields array
                bit_fields_str = ', '.join([f'"{bit}"' for bit in bits])

                f.write(f'    {{"{escaped_template}", 0x{fixed_bits:08x}U, 0x{fixed_mask:08x}U, {{{bit_fields_str}}}}},\n')

            f.write("};\n\n")
            f.write(f"const size_t NUM_ENCODINGS_{file_idx} = {end_idx - start_idx};\n")

    print(f"Generated {NUM_SPLIT_FILES} encoding data files with {total_encodings} total encodings")
    print(f"Average {encodings_per_file} encodings per file")

if __name__ == '__main__':
    main()
