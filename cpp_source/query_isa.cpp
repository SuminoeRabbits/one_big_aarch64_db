/*
 * AArch64 ISA Query Tool - C++ Implementation
 *
 * Fast standalone opcode decoder for AArch64 instructions
 * Equivalent to: python3 query_isa.py --op <OPCODE>
 */

#include <iostream>
#include <string>
#include <vector>
#include <cstdint>
#include <cstring>
#include <sstream>
#include <iomanip>
#include <map>
#include <algorithm>

#include "encoding_data.h"

// Parse opcode string (hex or binary, with optional separators)
uint32_t parse_opcode(const std::string& opcode_str) {
    std::string cleaned;

    // Remove separators ('_' and ':')
    for (char c : opcode_str) {
        if (c != '_' && c != ':') {
            cleaned += c;
        }
    }

    uint32_t value = 0;

    if (cleaned.substr(0, 2) == "0x" || cleaned.substr(0, 2) == "0X") {
        // Hex format
        value = std::stoul(cleaned.substr(2), nullptr, 16);
    } else if (cleaned.substr(0, 2) == "0b" || cleaned.substr(0, 2) == "0B") {
        // Binary format
        value = std::stoul(cleaned.substr(2), nullptr, 2);
    } else {
        std::cerr << "Error: Opcode must start with 0x (hex) or 0b (binary)" << std::endl;
        exit(1);
    }

    return value;
}

// Extract bit field value from opcode
uint32_t extract_field(uint32_t opcode, const std::string* bit_fields) {
    uint32_t value = 0;
    int shift = 0;

    for (int i = 31; i >= 0; i--) {
        if (bit_fields[31 - i] != "0" && bit_fields[31 - i] != "1") {
            // Variable field bit
            if ((opcode >> i) & 1) {
                value |= (1 << shift);
            }
            shift++;
        }
    }

    return value;
}

// Build assembly instruction from template and operands
std::string build_assembly(const std::string& asm_template, uint32_t opcode, const std::string* bit_fields) {
    std::string assembly = asm_template;

    // Extract register fields
    std::map<std::string, uint32_t> reg_values;
    std::map<std::string, uint32_t> imm_values;
    uint32_t shift_value = 0;
    bool has_shift = false;
    uint32_t crm_value = 0, op2_value = 0;
    bool has_crm = false, has_op2 = false;

    // Collect field values
    std::map<std::string, std::vector<int>> field_bits;
    for (int i = 0; i < 32; i++) {
        const std::string& field = bit_fields[i];
        if (field != "0" && field != "1") {
            field_bits[field].push_back(31 - i);  // Bit position
        }
    }

    // Extract values for each field
    for (const auto& field_pair : field_bits) {
        const std::string& field_name = field_pair.first;
        const std::vector<int>& bits = field_pair.second;

        uint32_t value = 0;
        for (size_t i = 0; i < bits.size(); i++) {
            int bit_pos = bits[i];
            if ((opcode >> bit_pos) & 1) {
                value |= (1 << (bits.size() - 1 - i));
            }
        }

        if (field_name == "Rd") {
            reg_values["Rd"] = value;
        } else if (field_name == "Rn") {
            reg_values["Rn"] = value;
        } else if (field_name == "Rm") {
            reg_values["Rm"] = value;
        } else if (field_name == "Rt") {
            reg_values["Rt"] = value;
        } else if (field_name.find("imm") == 0) {
            imm_values["imm"] = value;
        } else if (field_name.find("off") == 0 || field_name == "simm") {
            imm_values["offs"] = value;
        } else if (field_name == "sh") {
            shift_value = value;
            has_shift = true;
        } else if (field_name == "CRm") {
            crm_value = value;
            has_crm = true;
        } else if (field_name == "op2") {
            op2_value = value;
            has_op2 = true;
        }
    }

    // For HINT instruction, combine CRm and op2
    if (has_crm && has_op2 && imm_values.find("imm") == imm_values.end()) {
        imm_values["imm"] = (crm_value << 3) | op2_value;
    }

    // Replace register placeholders
    if (reg_values.find("Rd") != reg_values.end()) {
        uint32_t rd = reg_values["Rd"];
        std::string reg_str = (rd == 31) ? "sp" : ("x" + std::to_string(rd));
        std::string reg_str_w = (rd == 31) ? "wsp" : ("w" + std::to_string(rd));

        size_t pos;
        while ((pos = assembly.find("<Xd|SP>")) != std::string::npos) {
            assembly.replace(pos, 7, reg_str);
        }
        while ((pos = assembly.find("<Xd>")) != std::string::npos) {
            assembly.replace(pos, 4, reg_str);
        }
        while ((pos = assembly.find("<Wd|WSP>")) != std::string::npos) {
            assembly.replace(pos, 8, reg_str_w);
        }
        while ((pos = assembly.find("<Wd>")) != std::string::npos) {
            assembly.replace(pos, 4, reg_str_w);
        }
        while ((pos = assembly.find("<Wt>")) != std::string::npos) {
            assembly.replace(pos, 4, reg_str_w);
        }
    }

    if (reg_values.find("Rn") != reg_values.end()) {
        uint32_t rn = reg_values["Rn"];
        std::string reg_str = (rn == 31) ? "sp" : ("x" + std::to_string(rn));
        std::string reg_str_w = (rn == 31) ? "wsp" : ("w" + std::to_string(rn));

        size_t pos;
        while ((pos = assembly.find("<Xn|SP>")) != std::string::npos) {
            assembly.replace(pos, 7, reg_str);
        }
        while ((pos = assembly.find("<Xn>")) != std::string::npos) {
            assembly.replace(pos, 4, reg_str);
        }
        while ((pos = assembly.find("<Wn|WSP>")) != std::string::npos) {
            assembly.replace(pos, 8, reg_str_w);
        }
        while ((pos = assembly.find("<Wn>")) != std::string::npos) {
            assembly.replace(pos, 4, reg_str_w);
        }
    }

    if (reg_values.find("Rm") != reg_values.end()) {
        uint32_t rm = reg_values["Rm"];
        std::string reg_str = "x" + std::to_string(rm);
        std::string reg_str_w = "w" + std::to_string(rm);

        size_t pos;
        while ((pos = assembly.find("<Xm>")) != std::string::npos) {
            assembly.replace(pos, 4, reg_str);
        }
        while ((pos = assembly.find("<R><m>")) != std::string::npos) {
            assembly.replace(pos, 6, reg_str);
        }
        while ((pos = assembly.find("<Wm>")) != std::string::npos) {
            assembly.replace(pos, 4, reg_str_w);
        }
    }

    if (reg_values.find("Rt") != reg_values.end()) {
        uint32_t rt = reg_values["Rt"];
        std::string reg_str = "x" + std::to_string(rt);
        std::string reg_str_w = "w" + std::to_string(rt);

        size_t pos;
        while ((pos = assembly.find("<Xt>")) != std::string::npos) {
            assembly.replace(pos, 4, reg_str);
        }
        while ((pos = assembly.find("<Wt>")) != std::string::npos) {
            assembly.replace(pos, 4, reg_str_w);
        }
    }

    // Replace immediate values (always use hex format)
    if (imm_values.find("imm") != imm_values.end()) {
        std::stringstream ss;
        ss << "#0x" << std::hex << imm_values["imm"];
        std::string imm_hex = ss.str();

        size_t pos;
        while ((pos = assembly.find("#<imm>")) != std::string::npos) {
            assembly.replace(pos, 6, imm_hex);
        }

        ss.str("");
        ss << "0x" << std::hex << imm_values["imm"];
        std::string imm_hex_no_hash = ss.str();
        while ((pos = assembly.find("<imm>")) != std::string::npos) {
            assembly.replace(pos, 5, imm_hex_no_hash);
        }
    }

    if (imm_values.find("offs") != imm_values.end()) {
        std::stringstream ss;
        ss << "0x" << std::hex << imm_values["offs"];
        std::string offs_hex = ss.str();

        size_t pos;
        while ((pos = assembly.find("<offs>")) != std::string::npos) {
            assembly.replace(pos, 6, offs_hex);
        }
        while ((pos = assembly.find("<simm>")) != std::string::npos) {
            assembly.replace(pos, 6, offs_hex);
        }
    }

    // Handle shift field
    if (has_shift) {
        if (shift_value == 0) {
            // Remove shift part
            size_t pos;
            while ((pos = assembly.find("{, <shift>}")) != std::string::npos) {
                assembly.replace(pos, 11, "");
            }
        } else {
            size_t pos;
            while ((pos = assembly.find("<shift>")) != std::string::npos) {
                assembly.replace(pos, 7, "lsl #12");
            }
            while ((pos = assembly.find("{, ")) != std::string::npos) {
                assembly.replace(pos, 3, ", ");
            }
            while ((pos = assembly.find("}")) != std::string::npos) {
                assembly.erase(pos, 1);
            }
        }
    }

    // Clean up remaining optional parts
    size_t pos;
    while ((pos = assembly.find("{, <shift>}")) != std::string::npos) {
        assembly.erase(pos, 11);
    }
    while ((pos = assembly.find("{, <extend> {#<amount>}}")) != std::string::npos) {
        assembly.erase(pos, 24);
    }
    while ((pos = assembly.find("{, <shift> #<amount>}")) != std::string::npos) {
        assembly.erase(pos, 21);
    }

    // Clean up extra spaces
    std::stringstream ss;
    std::string word;
    bool first = true;
    for (char c : assembly) {
        if (c == ' ') {
            if (!word.empty()) {
                if (!first) ss << ' ';
                ss << word;
                word.clear();
                first = false;
            }
        } else {
            word += c;
        }
    }
    if (!word.empty()) {
        if (!first) ss << ' ';
        ss << word;
    }

    return ss.str();
}

void query_by_opcode(uint32_t opcode) {
    bool found = false;

    // Search through all encoding arrays
    const EncodingPattern* encoding_arrays[] = {
        ENCODINGS_0, ENCODINGS_1, ENCODINGS_2, ENCODINGS_3, ENCODINGS_4,
        ENCODINGS_5, ENCODINGS_6, ENCODINGS_7, ENCODINGS_8, ENCODINGS_9
    };
    const size_t array_sizes[] = {
        NUM_ENCODINGS_0, NUM_ENCODINGS_1, NUM_ENCODINGS_2, NUM_ENCODINGS_3, NUM_ENCODINGS_4,
        NUM_ENCODINGS_5, NUM_ENCODINGS_6, NUM_ENCODINGS_7, NUM_ENCODINGS_8, NUM_ENCODINGS_9
    };

    for (size_t arr_idx = 0; arr_idx < NUM_ENCODING_ARRAYS; arr_idx++) {
        const EncodingPattern* encodings = encoding_arrays[arr_idx];
        size_t num_encodings = array_sizes[arr_idx];

        for (size_t i = 0; i < num_encodings; i++) {
            const EncodingPattern& enc = encodings[i];

            // Check if opcode matches this encoding
            if ((opcode & enc.fixed_mask) == enc.fixed_bits) {
                std::string assembly = build_assembly(enc.asm_template, opcode, enc.bit_fields);
                std::cout << assembly << std::endl;
                found = true;
            }
        }
    }

    if (!found) {
        std::cerr << "No matching instruction found for opcode: 0x"
                  << std::hex << std::setw(8) << std::setfill('0') << opcode << std::endl;
    }
}

void print_usage() {
    std::cout << "Usage: query_isa --op <OPCODE>" << std::endl;
    std::cout << std::endl;
    std::cout << "Decode AArch64 instruction opcode to ARM Assembler notation" << std::endl;
    std::cout << std::endl;
    std::cout << "Options:" << std::endl;
    std::cout << "  --op <OPCODE>    Decode opcode (format: 0xHEX or 0bBINARY)" << std::endl;
    std::cout << "  --help           Show this help message" << std::endl;
    std::cout << std::endl;
    std::cout << "Examples:" << std::endl;
    std::cout << "  query_isa --op 0x91000000" << std::endl;
    std::cout << "  query_isa --op 0x91_00_00_00              # With separators" << std::endl;
    std::cout << "  query_isa --op 0b10010001000000000000000000000000" << std::endl;
    std::cout << std::endl;
    std::cout << "Separator characters (optional):" << std::endl;
    std::cout << "  '_' or ':' can be used as 8-bit separators" << std::endl;
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        print_usage();
        return 1;
    }

    std::string arg1 = argv[1];

    if (arg1 == "--help" || arg1 == "-h") {
        print_usage();
        return 0;
    }

    if (arg1 == "--op") {
        if (argc < 3) {
            std::cerr << "Error: --op requires an opcode argument" << std::endl;
            return 1;
        }

        std::string opcode_str = argv[2];
        uint32_t opcode = parse_opcode(opcode_str);
        query_by_opcode(opcode);
        return 0;
    }

    std::cerr << "Error: Unknown option: " << arg1 << std::endl;
    print_usage();
    return 1;
}
