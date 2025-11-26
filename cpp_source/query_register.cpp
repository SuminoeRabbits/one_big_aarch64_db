/*
 * AArch64 Register Query Tool - C++ Implementation v2
 *
 * Provides a fast --reg equivalent to `python3 query_register.py --reg <REG>`
 * Uses pre-generated static data instead of DuckDB for zero runtime dependencies
 */

#include <iostream>
#include <string>
#include <regex>
#include <vector>
#include <sstream>
#include <algorithm>
#include <set>
#include "register_data.h"

static const std::set<std::string> ALLOWED_DEFS = {"RES0","RES1","UNPREDICTABLE","UNDEFINED","RAO","UNKNOWN"};

static std::string escape_json(const std::string &s) {
    std::ostringstream o;
    for (auto c : s) {
        switch (c) {
            case '"': o << "\\\""; break;
            case '\\': o << "\\\\"; break;
            case '\b': o << "\\b"; break;
            case '\f': o << "\\f"; break;
            case '\n': o << "\\n"; break;
            case '\r': o << "\\r"; break;
            case '\t': o << "\\t"; break;
            default:
                if ((unsigned char)c < 0x20) {
                    o << "\\u" << std::hex << (int)c;
                } else {
                    o << c;
                }
        }
    }
    return o.str();
}

int run_fielddef_query(const std::string &def, bool json_out) {
    auto it = DEFINITION_TO_FIELDS.find(def);
    if (it == DEFINITION_TO_FIELDS.end()) {
        std::cerr << "Error: No fields found with definition '" << def << "'" << std::endl;
        return 1;
    }

    if (json_out) {
        std::cout << "[";
        bool first = true;
        for (const auto &entry : it->second) {
            if (!first) {
                std::cout << ",\n";
            }
            first = false;
            std::cout << "{\"register_name\":\"" << escape_json(entry.first) << "\",\"field_name\":\"" << escape_json(entry.second) << "\"}";
        }
        std::cout << "]\n";
    } else {
        for (const auto &entry : it->second) {
            std::cout << entry.first << "." << entry.second << std::endl;
        }
    }
    return 0;
}

int run_register_query(const std::string &query, bool json_out) {
    // Try to parse similar patterns as Python version
    std::string q = query;
    // Trim
    q.erase(q.begin(), std::find_if(q.begin(), q.end(), [](int ch) { return !std::isspace(ch); }));
    q.erase(std::find_if(q.rbegin(), q.rend(), [](int ch) { return !std::isspace(ch); }).base(), q.end());

    // Field definition only
    if (ALLOWED_DEFS.count(q)) {
        return run_fielddef_query(q, json_out);
    }

    // Patterns
    std::regex dot_bracket(R"(^([A-Z0-9_<>]+)\.([A-Z0-9_]+)\[(\d+)(?::(\d+))?\]$)");
    std::regex dot_only(R"(^([A-Z0-9_<>]+)\.([A-Z0-9_]+)$)");
    std::regex bracket(R"(^([A-Z0-9_<>]+)(?:\[(\d+)(?::(\d+))?\])?$)");
    std::smatch m;

    if (std::regex_match(q, m, dot_bracket)) {
        std::string reg = m[1];
        std::string field = m[2];
        int high = std::stoi(m[3]);
        int low = m[4].matched ? std::stoi(m[4]) : high;
        int start = std::min(high, low);
        int end = std::max(high, low);

        // Verify field exists in register
        auto reg_it = REGISTER_DATABASE.find(reg);
        if (reg_it == REGISTER_DATABASE.end()) {
            std::cerr << "Error: Register '" << reg << "' not found in database." << std::endl;
            return 1;
        }

        bool matched = false;
        for (const auto &fld : reg_it->second.fields) {
            if (fld.field_name == field && fld.field_msb == end && fld.field_lsb == start) {
                matched = true;
                if (json_out) {
                    std::cout << "{";
                    std::cout << "\"register_name\":\"" << escape_json(reg) << "\",";
                    std::cout << "\"field_name\":\"" << escape_json(field) << "\",";
                    std::cout << "\"field_position\":\"" << escape_json(fld.field_position) << "\",";
                    std::cout << "\"field_definition\":\"" << escape_json(fld.field_definition) << "\"}" << std::endl;
                } else {
                    std::cout << "Register: " << reg << std::endl;
                    std::cout << "Field Name: " << field << std::endl;
                    std::cout << "Field Position: " << fld.field_position << std::endl;
                }
                break;
            }
        }
        if (!matched) {
            std::cerr << "Error: Field '" << field << "' exists but not at bit range [" << end << ":" << start << "] or not found." << std::endl;
            return 1;
        }
        return 0;
    }

    if (std::regex_match(q, m, dot_only)) {
        std::string reg = m[1];
        std::string field = m[2];

        // Query specific field in register (take highest MSB)
        auto reg_it = REGISTER_DATABASE.find(reg);
        if (reg_it == REGISTER_DATABASE.end()) {
            std::cerr << "Error: Register '" << reg << "' not found in database." << std::endl;
            return 1;
        }

        const RegisterField *found_field = nullptr;
        for (const auto &fld : reg_it->second.fields) {
            if (fld.field_name == field) {
                found_field = &fld;
                break;  // Fields are already sorted by MSB DESC
            }
        }

        if (!found_field) {
            std::cerr << "Error: Field '" << field << "' not found in register '" << reg << "'" << std::endl;
            return 1;
        }

        if (json_out) {
            std::cout << "{";
            std::cout << "\"register_name\":\"" << escape_json(reg) << "\",";
            std::cout << "\"field_name\":\"" << escape_json(field) << "\",";
            std::cout << "\"field_position\":\"" << escape_json(found_field->field_position) << "\"}" << std::endl;
        } else {
            std::cout << "Register: " << reg << std::endl;
            std::cout << "Field Name: " << field << std::endl;
            std::cout << "Field Position: " << found_field->field_position << std::endl;
        }
        return 0;
    }

    if (std::regex_match(q, m, bracket)) {
        std::string reg = m[1];
        if (m[2].matched) {
            int high = std::stoi(m[2]);
            int low = m[3].matched ? std::stoi(m[3]) : high;
            int start = std::min(high, low);
            int end = std::max(high, low);

            auto reg_it = REGISTER_DATABASE.find(reg);
            if (reg_it == REGISTER_DATABASE.end()) {
                std::cerr << "Error: Register '" << reg << "' not found in database." << std::endl;
                return 1;
            }

            std::vector<const RegisterField*> matching_fields;
            for (const auto &fld : reg_it->second.fields) {
                if (fld.field_lsb <= end && fld.field_msb >= start) {
                    matching_fields.push_back(&fld);
                }
            }

            if (matching_fields.empty()) {
                std::cerr << "Error: No fields found for bit range [" << end << ":" << start << "] in register '" << reg << "'" << std::endl;
                return 1;
            }

            if (start == end) {
                // single bit
                if (json_out) {
                    std::cout << "{";
                    std::cout << "\"register_name\":\"" << escape_json(reg) << "\",";
                    std::cout << "\"bit_position\":\"" << start << "\",";
                    std::cout << "\"field_name\":\"" << escape_json(matching_fields[0]->field_name) << "\",\"field_position\":\"" << escape_json(matching_fields[0]->field_position) << "\"}" << std::endl;
                } else {
                    std::cout << "Register: " << reg << std::endl;
                    std::cout << "Bit Position: [" << start << "]" << std::endl;
                    std::cout << "Field Name: " << matching_fields[0]->field_name << std::endl;
                }
            } else {
                // range
                if (json_out) {
                    std::cout << "{";
                    std::cout << "\"register_name\":\"" << escape_json(reg) << "\",";
                    std::cout << "\"bit_start\":\"" << start << "\",";
                    std::cout << "\"bit_end\":\"" << end << "\",";
                    std::cout << "\"fields\": [";
                    for (size_t i = 0; i < matching_fields.size(); ++i) {
                        if (i > 0) {
                            std::cout << ",";
                        }
                        std::cout << "{\"name\":\"" << escape_json(matching_fields[i]->field_name) << "\",\"position\":\"" << escape_json(matching_fields[i]->field_position) << "\"}";
                    }
                    std::cout << "]}" << std::endl;
                } else {
                    std::cout << "Register: " << reg << std::endl;
                    std::cout << "Bit Range: [" << end << ":" << start << "]" << std::endl;
                    for (const auto *fld : matching_fields) {
                        std::cout << "  " << fld->field_position << "  " << fld->field_name << std::endl;
                    }
                }
            }
            return 0;
        } else {
            // entire register
            auto reg_it = REGISTER_DATABASE.find(reg);
            if (reg_it == REGISTER_DATABASE.end()) {
                std::cerr << "Error: Register '" << reg << "' not found in database." << std::endl;
                return 1;
            }

            if (json_out) {
                std::cout << "{";
                std::cout << "\"register_name\":\"" << escape_json(reg) << "\",";
                std::cout << "\"features\":\"" << escape_json(reg_it->second.feature_name) << "\",";
                std::cout << "\"fields\": [";
                for (size_t i = 0; i < reg_it->second.fields.size(); ++i) {
                    if (i > 0) {
                        std::cout << ",";
                    }
                    const auto &fld = reg_it->second.fields[i];
                    std::cout << "{\"name\":\"" << escape_json(fld.field_name) << "\",\"position\":\"" << escape_json(fld.field_position) << "\"}";
                }
                std::cout << "]}" << std::endl;
            } else {
                std::cout << "Register: " << reg << std::endl;
                std::cout << "Features: " << reg_it->second.feature_name << std::endl;
                std::cout << "Fields:\n";
                for (const auto &fld : reg_it->second.fields) {
                    std::cout << "  " << fld.field_position << "  " << fld.field_name << std::endl;
                }
            }
            return 0;
        }
    }

    std::cerr << "Error: Invalid query format: '" << query << "'" << std::endl;
    return 1;
}

void print_usage() {
    std::cout << "Usage: query_register --reg <REG> [--json]" << std::endl;
    std::cout << "Examples:\n  query_register --reg 'HCR_EL2[1]'\n  query_register --reg 'HCR_EL2.TGE'\n";
}

int main(int argc, char* argv[]) {
    if (argc < 3) {
        print_usage();
        return 1;
    }

    std::string arg1 = argv[1];
    if (arg1 == "--help" || arg1 == "-h") {
        print_usage();
        return 0;
    }

    bool json_out = false;
    std::string reg_query;

    if (arg1 == "--reg" || arg1 == "-r") {
        reg_query = argv[2];
        // Check for --json in later args
        for (int i = 3; i < argc; i++) {
            if (std::string(argv[i]) == "--json") {
                json_out = true;
            }
        }
    } else {
        print_usage();
        return 1;
    }

    return run_register_query(reg_query, json_out);
}
