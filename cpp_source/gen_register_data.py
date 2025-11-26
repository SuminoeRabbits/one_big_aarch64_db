#!/usr/bin/env python3
"""
Generate C++ register data from aarch64_sysreg_db.duckdb
Split into multiple source files for parallel compilation
"""
import duckdb
import sys
import os

NUM_SPLIT_FILES = 5  # Split into 5 files for parallel compilation

def escape_cpp_string(s):
    """Escape string for C++ literal"""
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

def main():
    db_path = '../aarch64_sysreg_db.duckdb'
    if not os.path.exists(db_path):
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = duckdb.connect(db_path)

    # Get all registers with their metadata
    registers_query = '''
        SELECT DISTINCT register_name, feature_name, long_name, register_width, reg_purpose
        FROM aarch64_sysreg
        ORDER BY register_name
    '''
    registers = conn.execute(registers_query).fetchall()

    # Get all fields
    fields_query = '''
        SELECT register_name, field_name, field_msb, field_lsb,
               field_position, field_description, field_definition
        FROM aarch64_sysreg_fields
        ORDER BY register_name, field_msb DESC
    '''
    fields = conn.execute(fields_query).fetchall()

    conn.close()

    # Group fields by register
    fields_by_register = {}
    for field in fields:
        reg_name = field[0]
        if reg_name not in fields_by_register:
            fields_by_register[reg_name] = []
        fields_by_register[reg_name].append(field)

    # Group registers by name (some may have multiple features)
    reg_dict = {}
    for reg in registers:
        reg_name = reg[0]
        if reg_name not in reg_dict:
            reg_dict[reg_name] = {
                'features': [],
                'long_name': reg[2],
                'width': reg[3],
                'purpose': reg[4]
            }
        reg_dict[reg_name]['features'].append(reg[1])

    # Sort registers for consistent splitting
    sorted_regs = sorted(reg_dict.items())
    total_regs = len(sorted_regs)
    regs_per_file = (total_regs + NUM_SPLIT_FILES - 1) // NUM_SPLIT_FILES

    # Generate header file
    with open('register_data.h', 'w') as f:
        f.write(f"// Auto-generated register data ({total_regs} registers, {len(fields)} fields)\n")
        f.write("#ifndef REGISTER_DATA_H\n")
        f.write("#define REGISTER_DATA_H\n\n")
        f.write("#include <string>\n")
        f.write("#include <vector>\n")
        f.write("#include <unordered_map>\n\n")

        f.write("struct RegisterField {\n")
        f.write("    std::string field_name;\n")
        f.write("    int field_msb;\n")
        f.write("    int field_lsb;\n")
        f.write("    std::string field_position;\n")
        f.write("    std::string field_description;\n")
        f.write("    std::string field_definition;\n")
        f.write("};\n\n")

        f.write("struct RegisterInfo {\n")
        f.write("    std::string register_name;\n")
        f.write("    std::string feature_name;\n")
        f.write("    std::string long_name;\n")
        f.write("    std::string register_width;\n")
        f.write("    std::string reg_purpose;\n")
        f.write("    std::vector<RegisterField> fields;\n")
        f.write("};\n\n")

        # Declare extern partial maps
        for i in range(NUM_SPLIT_FILES):
            f.write(f"extern const std::unordered_map<std::string, RegisterInfo> REGISTER_DATABASE_{i};\n")

        f.write("\n// Combined database accessor\n")
        f.write("const std::unordered_map<std::string, RegisterInfo>& get_register_database();\n")
        f.write("#define REGISTER_DATABASE get_register_database()\n")
        f.write("\nextern const std::unordered_map<std::string, std::vector<std::string>> FIELD_TO_REGISTERS;\n")
        f.write("extern const std::unordered_map<std::string, std::vector<std::pair<std::string, std::string>>> DEFINITION_TO_FIELDS;\n\n")
        f.write("#endif // REGISTER_DATA_H\n")

    # Generate split source files for register database
    for file_idx in range(NUM_SPLIT_FILES):
        start_idx = file_idx * regs_per_file
        end_idx = min(start_idx + regs_per_file, total_regs)

        with open(f'register_data_{file_idx}.cpp', 'w') as f:
            f.write(f"// Auto-generated register data part {file_idx + 1}/{NUM_SPLIT_FILES}\n")
            f.write("#include \"register_data.h\"\n\n")
            f.write(f"const std::unordered_map<std::string, RegisterInfo> REGISTER_DATABASE_{file_idx} = {{\n")

            for reg_name, reg_info in sorted_regs[start_idx:end_idx]:
                f.write(f'    {{"{escape_cpp_string(reg_name)}", {{\n')
                f.write(f'        "{escape_cpp_string(reg_name)}",\n')
                # Concatenate all features
                features_str = ", ".join(reg_info['features']) if reg_info['features'] else ""
                f.write(f'        "{escape_cpp_string(features_str)}",\n')
                f.write(f'        "{escape_cpp_string(str(reg_info["long_name"]))}",\n')
                f.write(f'        "{escape_cpp_string(str(reg_info["width"]))}",\n')
                f.write(f'        "{escape_cpp_string(str(reg_info["purpose"]))}",\n')

                # Add fields
                f.write('        {\n')
                if reg_name in fields_by_register:
                    for field in fields_by_register[reg_name]:
                        field_name = field[1]
                        field_msb = field[2]
                        field_lsb = field[3]
                        field_position = field[4]
                        field_description = field[5] if field[5] else ""
                        field_definition = field[6] if field[6] else ""

                        f.write(f'            {{"{escape_cpp_string(field_name)}", ')
                        f.write(f'{field_msb}, {field_lsb}, ')
                        f.write(f'"{escape_cpp_string(field_position)}", ')
                        f.write(f'"{escape_cpp_string(field_description)}", ')
                        f.write(f'"{escape_cpp_string(field_definition)}"}},\n')

                f.write('        }\n')
                f.write('    }},\n')

            f.write("};\n")

    # Generate main source file with combined database and other mappings
    with open('register_data.cpp', 'w') as f:
        f.write(f"// Auto-generated register data - main file\n")
        f.write("#include \"register_data.h\"\n\n")

        # Combine all partial databases using lazy initialization function
        f.write("const std::unordered_map<std::string, RegisterInfo>& get_register_database() {\n")
        f.write("    static std::unordered_map<std::string, RegisterInfo> combined;\n")
        f.write("    static bool initialized = false;\n")
        f.write("    if (!initialized) {\n")
        for i in range(NUM_SPLIT_FILES):
            f.write(f"        combined.insert(REGISTER_DATABASE_{i}.begin(), REGISTER_DATABASE_{i}.end());\n")
        f.write("        initialized = true;\n")
        f.write("    }\n")
        f.write("    return combined;\n")
        f.write("}\n\n")

        # Generate field-to-registers mapping
        field_to_regs = {}
        for field in fields:
            field_name = field[1]
            reg_name = field[0]
            if field_name not in field_to_regs:
                field_to_regs[field_name] = []
            if reg_name not in field_to_regs[field_name]:
                field_to_regs[field_name].append(reg_name)

        f.write("const std::unordered_map<std::string, std::vector<std::string>> FIELD_TO_REGISTERS = {\n")
        for field_name, reg_list in sorted(field_to_regs.items()):
            f.write(f'    {{"{escape_cpp_string(field_name)}", {{')
            for i, reg in enumerate(reg_list):
                if i > 0:
                    f.write(', ')
                f.write(f'"{escape_cpp_string(reg)}"')
            f.write('}},\n')
        f.write("};\n\n")

        # Generate definition-to-fields mapping (for RES0, RES1, etc.)
        def_to_fields = {}
        for field in fields:
            field_def = field[6]
            if field_def and field_def.strip():
                if field_def not in def_to_fields:
                    def_to_fields[field_def] = []
                def_to_fields[field_def].append((field[0], field[1], field[4]))  # reg_name, field_name, position

        f.write("const std::unordered_map<std::string, std::vector<std::pair<std::string, std::string>>> DEFINITION_TO_FIELDS = {\n")
        for def_name, field_list in sorted(def_to_fields.items()):
            f.write(f'    {{"{escape_cpp_string(def_name)}", {{')
            for i, (reg, fld, pos) in enumerate(field_list):
                if i > 0:
                    f.write(', ')
                # Store as "REG.FIELDposition" for easier output
                f.write(f'{{"{escape_cpp_string(reg)}", "{escape_cpp_string(fld + pos)}"}}')
            f.write('}},\n')
        f.write("};\n")

    print(f"Generated register_data.h and {NUM_SPLIT_FILES + 1} source files")
    print(f"  {total_regs} unique registers")
    print(f"  {len(fields)} total fields")
    print(f"  {len(field_to_regs)} unique field names")
    print(f"  {len(def_to_fields)} field definitions")
    print(f"  Average {regs_per_file} registers per split file")

if __name__ == '__main__':
    main()
