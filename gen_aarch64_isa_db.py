import os
import glob
import json
import duckdb
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime

# Configuration
SOURCE_DIR = 'source_202509/ISA_A64_xml_A_profile_FAT-2025-09_ASL1'
DB_FILENAME = 'aarch64_isa_db.duckdb'
EXCEL_FILENAME = 'aarch64_isa_db.xlsx'

# Files to exclude
EXCLUDE_FILES = {
    'index.xml',
    'encodingindex.xml',
    'shared_pseudocode.xml',
    'notice.xml',
    'constraint_text_mappings.xml',
    'fpsimdindex.xml',
    'sveindex.xml',
    'mortlachindex.xml',
    'permindex.xml' 
}

def create_schema(con):
    con.execute("DROP TABLE IF EXISTS aarch64_isa_encoding_fields")
    con.execute("DROP TABLE IF EXISTS aarch64_isa_encodings")
    con.execute("DROP TABLE IF EXISTS aarch64_isa_instructions")
    con.execute("DROP SEQUENCE IF EXISTS seq_instr_id")
    con.execute("DROP SEQUENCE IF EXISTS seq_enc_id")
    
    con.execute("CREATE SEQUENCE seq_instr_id START 1")
    con.execute("CREATE SEQUENCE seq_enc_id START 1")

    con.execute("""
        CREATE TABLE aarch64_isa_instructions (
            id INTEGER PRIMARY KEY DEFAULT nextval('seq_instr_id'),
            xml_filename VARCHAR,
            mnemonic VARCHAR,
            title VARCHAR,
            description VARCHAR,
            instr_class VARCHAR,
            isa VARCHAR,
            feature_name VARCHAR,
            exception_level VARCHAR,
            docvars JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create columns for bit_31 down to bit_0
    bit_columns = ", ".join([f"bit_{i} VARCHAR" for i in range(31, -1, -1)])

    con.execute(f"""
        CREATE TABLE aarch64_isa_encodings (
            id INTEGER PRIMARY KEY DEFAULT nextval('seq_enc_id'),
            instruction_id INTEGER,
            encoding_name VARCHAR,
            encoding_label VARCHAR,
            iclass_name VARCHAR,
            asm_template VARCHAR,
            bitdiffs VARCHAR,
            {bit_columns},
            FOREIGN KEY (instruction_id) REFERENCES aarch64_isa_instructions(id)
        )
    """)

def parse_xml_file(filepath, con):
    filename = os.path.basename(filepath)
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Error parsing {filename}: {e}")
        return

    if root.tag != 'instructionsection':
        return

    # Check file type (instruction or alias)
    file_type = root.get('type', 'instruction')

    # Extract Docvars (Global)
    global_docvars = {}
    for dv in root.findall('./docvars/docvar'):
        global_docvars[dv.get('key')] = dv.get('value')
    
    # Filter: Only A64
    isa = global_docvars.get('isa', '')
    if isa != 'A64':
        return

    # Extract Common Instruction Info
    title = root.get('title', '')
    instr_class = global_docvars.get('instr-class', '')
    
    desc_elem = root.find('./desc/brief/para')
    description = desc_elem.text if desc_elem is not None else ''

    # Extract Feature Name (Global for file)
    features = set()
    for av in root.findall('.//arch_variant'):
        feat = av.get('feature')
        if feat:
            features.add(feat)
    
    if not features:
        feature_name = 'AARCH64'
    else:
        feature_name = ' || '.join(sorted(features))

    exception_level = 'ALL'

    # Pre-process Encodings to group them by Mnemonic
    # We need to parse classes and encodings first to find their mnemonics
    
    # Structure: { mnemonic: [ (iclass_node, encoding_node, regdiagram_node) ] }
    mnemonic_groups = {}

    for iclass in root.findall('.//iclass'):
        iclass_name = iclass.get('name', '')
        regdiagram = iclass.find('regdiagram')
        if regdiagram is None:
            continue

        for encoding in iclass.findall('encoding'):
            # Determine Mnemonic for this encoding
            enc_docvars = {}
            for dv in encoding.findall('./docvars/docvar'):
                enc_docvars[dv.get('key')] = dv.get('value')
            
            mnemonic = enc_docvars.get('mnemonic', '')
            alias_mnemonic = enc_docvars.get('alias_mnemonic', '')

            # Logic: If alias file, prefer alias_mnemonic. If instruction file, prefer mnemonic.
            # But sometimes alias_mnemonic is present even in instruction files? 
            # Let's stick to: if alias_mnemonic exists and file_type is alias, use it.
            # Actually, stset_ldset.xml is type="alias".
            
            final_mnemonic = mnemonic
            if file_type == 'alias' and alias_mnemonic:
                final_mnemonic = alias_mnemonic
            elif not final_mnemonic and alias_mnemonic:
                 # Fallback if mnemonic is missing but alias is there
                final_mnemonic = alias_mnemonic
            
            # If still empty, try global docvar (though we saw it might be missing)
            if not final_mnemonic:
                final_mnemonic = global_docvars.get('mnemonic', '')

            if not final_mnemonic:
                # Last resort: use title but that's messy. 
                # Or skip? If no mnemonic, it's hard to index.
                # Let's use a placeholder or skip.
                print(f"Warning: No mnemonic found for encoding {encoding.get('name')} in {filename}")
                continue

            if final_mnemonic not in mnemonic_groups:
                mnemonic_groups[final_mnemonic] = []
            
            mnemonic_groups[final_mnemonic].append({
                'iclass': iclass,
                'encoding': encoding,
                'regdiagram': regdiagram,
                'iclass_name': iclass_name
            })

    # Now create Instruction entries for each unique mnemonic
    for mnemonic, enc_list in mnemonic_groups.items():
        # Insert Instruction
        # We use the same title/desc/features for all variants in the file for now, 
        # unless we want to try and refine it per mnemonic (harder).
        
        res = con.execute("""
            INSERT INTO aarch64_isa_instructions (xml_filename, mnemonic, title, description, instr_class, isa, feature_name, exception_level, docvars)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
        """, (filename, mnemonic, title, description, instr_class, isa, feature_name, exception_level, json.dumps(global_docvars))).fetchone()
        
        instr_id = res[0]

        # Process Encodings for this mnemonic
        for item in enc_list:
            encoding = item['encoding']
            iclass_name = item['iclass_name']
            regdiagram = item['regdiagram']
            
            enc_name = encoding.get('name', '')
            enc_label = encoding.get('label', '')
            bitdiffs = encoding.get('bitdiffs', '')
            
            asm_template_elem = encoding.find('asmtemplate')
            asm_template = "".join(asm_template_elem.itertext()) if asm_template_elem is not None else ''

            # Parse Diagram Boxes (Fields) - Re-doing this per encoding is slightly inefficient but safe
            diagram_fields = []
            for box in regdiagram.findall('box'):
                hibit = int(box.get('hibit'))
                width = int(box.get('width', '1'))
                name = box.get('name', '')
                
                fixed_val_bits = []
                for c in box.findall('c'):
                    colspan = int(c.get('colspan', '1'))
                    val = c.text if c.text else 'x'
                    fixed_val_bits.extend([val] * colspan)
                
                diagram_value = "".join(fixed_val_bits)
                diagram_fields.append({
                    'hibit': hibit,
                    'width': width,
                    'name': name,
                    'diagram_value': diagram_value
                })

            # Process Fields for this encoding
            enc_boxes = {}
            for box in encoding.findall('box'):
                hibit = int(box.get('hibit'))
                val_bits = []
                for c in box.findall('c'):
                    colspan = int(c.get('colspan', '1'))
                    val = c.text if c.text else 'x'
                    val_bits.extend([val] * colspan)
                enc_boxes[hibit] = "".join(val_bits)

            # Construct 32-bit array
            bit_array = [''] * 32
            for field in diagram_fields:
                hibit = field['hibit']
                width = field['width']
                name = field['name']
                final_value = field['diagram_value']
                
                if hibit in enc_boxes:
                    final_value = enc_boxes[hibit]
                
                for i in range(width):
                    bit_pos = hibit - i
                    val_char = final_value[i]
                    if val_char in ('0', '1'):
                        bit_array[bit_pos] = val_char
                    else:
                        bit_array[bit_pos] = name if name else 'x'

            ordered_bits = [bit_array[i] for i in range(31, -1, -1)]
            bit_placeholders = ", ".join(["?"] * 32)
            
            con.execute(f"""
                INSERT INTO aarch64_isa_encodings (instruction_id, encoding_name, encoding_label, iclass_name, asm_template, bitdiffs, 
                bit_31, bit_30, bit_29, bit_28, bit_27, bit_26, bit_25, bit_24, 
                bit_23, bit_22, bit_21, bit_20, bit_19, bit_18, bit_17, bit_16, 
                bit_15, bit_14, bit_13, bit_12, bit_11, bit_10, bit_9, bit_8, 
                bit_7, bit_6, bit_5, bit_4, bit_3, bit_2, bit_1, bit_0)
                VALUES (?, ?, ?, ?, ?, ?, {bit_placeholders})
            """, (instr_id, enc_name, enc_label, iclass_name, asm_template, bitdiffs, *ordered_bits))

def main():
    print("================================================================================")
    print("AArch64 ISA Database Generator")
    print("================================================================================")

    if not os.path.exists(SOURCE_DIR):
        print(f"Error: Source directory '{SOURCE_DIR}' not found.")
        return

    con = duckdb.connect(DB_FILENAME)
    create_schema(con)

    xml_files = glob.glob(os.path.join(SOURCE_DIR, '*.xml'))
    xml_files = [f for f in xml_files if os.path.basename(f) not in EXCLUDE_FILES]
    
    print(f"Found {len(xml_files)} XML files to process.")
    
    count = 0
    processed_count = 0
    for f in xml_files:
        parse_xml_file(f, con)
        count += 1
        processed_count += 1 # We might want to track how many actually got inserted, but parse_xml_file doesn't return that.
        if count % 100 == 0:
            print(f"Processed {count} files...")

    print(f"Finished processing {count} files.")
    
    # Export to Excel
    print(f"Exporting to {EXCEL_FILENAME}...")
    
    df_instr = con.execute("SELECT * FROM aarch64_isa_instructions").fetchdf()
    df_enc = con.execute("SELECT * FROM aarch64_isa_encodings").fetchdf()
    
    with pd.ExcelWriter(EXCEL_FILENAME, engine='openpyxl') as writer:
        df_instr.to_excel(writer, sheet_name='Instructions', index=False)
        df_enc.to_excel(writer, sheet_name='Encodings', index=False)
        
    print("Done.")
    con.close()

if __name__ == '__main__':
    main()
