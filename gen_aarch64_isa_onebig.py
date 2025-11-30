#!/usr/bin/env python3
"""
Generate RAG-optimized JSONL from aarch64_isa_db.duckdb

This script creates a JSONL (JSON Lines) file that consolidates all
AArch64 ISA instruction information in a format optimized for RAG systems
using LlamaIndex.

Output: aarch64_isa_onebig.jsonl
Format: One JSON object per line, each representing a semantically complete chunk
"""

import duckdb
import sys
import os
import json
from datetime import datetime
import hashlib


def generate_id(mnemonic, encoding_name=None):
    """Generate a unique ID for the document."""
    if encoding_name:
        base = f"isa_{mnemonic}_{encoding_name}"
    else:
        base = f"isa_{mnemonic}"
    return hashlib.md5(base.encode()).hexdigest()


def clean_text(text):
    """Clean text for better RAG performance."""
    if text is None or text == 'None':
        return ""
    return str(text).strip()


def main():
    db_path = 'aarch64_isa_db.duckdb'
    output_path = 'aarch64_isa_onebig.jsonl'

    if not os.path.exists(db_path):
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        print("Please run 'make db' first to generate the database.", file=sys.stderr)
        sys.exit(1)

    print("=" * 80)
    print("AArch64 ISA OneBig JSONL Generator")
    print("=" * 80)
    print(f"Input:  {db_path}")
    print(f"Output: {output_path}")
    print()

    # Connect to database
    conn = duckdb.connect(db_path, read_only=True)

    # Get statistics
    stats = {
        'total_instructions': conn.execute("SELECT COUNT(*) FROM aarch64_isa_instructions").fetchone()[0],
        'total_encodings': conn.execute("SELECT COUNT(*) FROM aarch64_isa_encodings").fetchone()[0],
        'unique_mnemonics': conn.execute("SELECT COUNT(DISTINCT mnemonic) FROM aarch64_isa_instructions").fetchone()[0],
    }

    print(f"Database Statistics:")
    print(f"  Total Instructions: {stats['total_instructions']}")
    print(f"  Unique Mnemonics:   {stats['unique_mnemonics']}")
    print(f"  Total Encodings:    {stats['total_encodings']}")
    print()

    # Strategy: Create one document per instruction with all encodings
    # This provides semantically complete chunks for RAG

    # Get all instructions with their encodings
    query = """
        SELECT
            i.id,
            i.mnemonic,
            i.title,
            i.description,
            i.instr_class,
            i.isa,
            i.feature_name,
            i.exception_level,
            i.xml_filename,
            COUNT(e.id) as encoding_count
        FROM aarch64_isa_instructions i
        LEFT JOIN aarch64_isa_encodings e ON i.id = e.instruction_id
        GROUP BY i.id, i.mnemonic, i.title, i.description, i.instr_class, i.isa, i.feature_name, i.exception_level, i.xml_filename
        ORDER BY i.mnemonic
    """

    instructions = conn.execute(query).fetchall()

    # Get all encodings
    encodings_query = """
        SELECT
            instruction_id,
            encoding_name,
            encoding_label,
            iclass_name,
            asm_template,
            bitdiffs
        FROM aarch64_isa_encodings
        ORDER BY instruction_id, encoding_name
    """

    encodings = conn.execute(encodings_query).fetchall()

    # Group encodings by instruction_id
    encodings_by_instr = {}
    for enc in encodings:
        instr_id = enc[0]
        if instr_id not in encodings_by_instr:
            encodings_by_instr[instr_id] = []
        encodings_by_instr[instr_id].append(enc)

    conn.close()

    # Write JSONL file
    print(f"Generating JSONL for {len(instructions)} instructions...")

    documents = []

    for idx, instr in enumerate(instructions, 1):
        (instr_id, mnemonic, title, description, instr_class, isa,
         feature_name, exception_level, xml_filename, encoding_count) = instr

        # Build comprehensive text content for embedding
        text_parts = []

        # Instruction overview
        text_parts.append(f"Instruction: {mnemonic}")
        if title and title != 'None':
            text_parts.append(f"Title: {clean_text(title)}")

        if description and description != 'None':
            text_parts.append(f"Description: {clean_text(description)}")

        text_parts.append(f"ISA: {isa}")

        if instr_class and instr_class != 'None':
            text_parts.append(f"Instruction Class: {clean_text(instr_class)}")

        if feature_name and feature_name != 'None':
            text_parts.append(f"Required Features: {feature_name}")

        if exception_level and exception_level != 'None':
            text_parts.append(f"Exception Level: {exception_level}")

        # Add encoding information
        if instr_id in encodings_by_instr:
            text_parts.append(f"\nEncodings ({len(encodings_by_instr[instr_id])} total):")

            for enc in encodings_by_instr[instr_id]:
                (_, enc_name, enc_label, iclass_name, asm_template, bitdiffs) = enc

                enc_info = f"  - {enc_name}"
                if enc_label:
                    enc_info += f" ({enc_label})"
                if iclass_name:
                    enc_info += f" [class: {iclass_name}]"
                if asm_template and asm_template != 'None':
                    enc_info += f"\n    Assembly: {clean_text(asm_template)}"
                if bitdiffs and bitdiffs != 'None':
                    enc_info += f"\n    Bit Diffs: {bitdiffs}"

                text_parts.append(enc_info)

        text_content = "\n".join(text_parts)

        # Build metadata (FLAT structure - no nesting!)
        # Prepare encoding names as comma-separated string
        encoding_names = ""
        if instr_id in encodings_by_instr:
            encoding_names = ", ".join([enc[1] for enc in encodings_by_instr[instr_id] if enc[1]])

        metadata = {
            "mnemonic": mnemonic if mnemonic else "",
            "title": clean_text(title)[:500] if title else "",  # Truncate long text
            "description": clean_text(description)[:500] if description else "",
            "instr_class": clean_text(instr_class) if instr_class else "",
            "isa": isa if isa else "A64",
            "feature_name": feature_name if feature_name else "AARCH64",
            "exception_level": exception_level if exception_level else "ALL",
            "encoding_count": int(encoding_count),
            "encoding_names": encoding_names,
            "xml_filename": xml_filename if xml_filename else "",
            "architecture": "AArch64",
            "spec_version": "2025-09",
            "doc_type": "isa_instruction",
            "has_encodings": len(encodings_by_instr.get(instr_id, [])) > 0,
        }

        # Create document object (LlamaIndex format)
        document = {
            "id": generate_id(mnemonic, None),
            "text": text_content,
            "metadata": metadata
        }

        documents.append(document)

        # Progress indicator
        if idx % 100 == 0:
            print(f"  Processed {idx}/{len(instructions)} instructions...")

    # Write JSONL file (one JSON per line)
    print()
    print("Writing JSONL file...")

    with open(output_path, 'w', encoding='utf-8') as f:
        for doc in documents:
            f.write(json.dumps(doc, ensure_ascii=False) + '\n')

    file_size = os.path.getsize(output_path)
    print()
    print("=" * 80)
    print("Generation Complete!")
    print("=" * 80)
    print(f"Output file:   {output_path}")
    print(f"File size:     {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
    print(f"Documents:     {len(documents)}")
    print(f"Format:        JSONL (JSON Lines)")
    print()
    print("LlamaIndex Usage:")
    print("  from llama_index.core import SimpleDirectoryReader")
    print(f"  documents = SimpleDirectoryReader(input_files=['{output_path}']).load_data()")
    print()


if __name__ == '__main__':
    main()
