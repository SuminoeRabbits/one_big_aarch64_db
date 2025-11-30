#!/usr/bin/env python3
"""
Generate RAG-optimized JSON from aarch64_sysreg_db.duckdb

This script creates a JSONL (JSON Lines) file that consolidates all
AArch64 system register information in a format optimized for RAG systems
using LlamaIndex.

Output: aarch64_sysreg_onebig.jsonl
Format: One JSON object per line, each representing a semantically complete chunk
"""

import duckdb
import sys
import os
import json
from datetime import datetime
import hashlib


def generate_id(register_name, field_name=None):
    """Generate a unique ID for the document."""
    if field_name:
        base = f"sysreg_{register_name}_{field_name}"
    else:
        base = f"sysreg_{register_name}"
    return hashlib.md5(base.encode()).hexdigest()


def clean_text(text):
    """Clean text for better RAG performance."""
    if text is None or text == 'None':
        return ""
    return str(text).strip()


def main():
    db_path = 'aarch64_sysreg_db.duckdb'
    output_path = 'aarch64_sysreg_onebig.jsonl'

    if not os.path.exists(db_path):
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        print("Please run 'make db' first to generate the database.", file=sys.stderr)
        sys.exit(1)

    print("=" * 80)
    print("AArch64 System Register OneBig JSONL Generator")
    print("=" * 80)
    print(f"Input:  {db_path}")
    print(f"Output: {output_path}")
    print()

    # Connect to database
    conn = duckdb.connect(db_path, read_only=True)

    # Get statistics
    stats = {
        'total_registers': conn.execute("SELECT COUNT(DISTINCT register_name) FROM aarch64_sysreg").fetchone()[0],
        'total_features': conn.execute("SELECT COUNT(DISTINCT feature_name) FROM aarch64_sysreg").fetchone()[0],
        'total_fields': conn.execute("SELECT COUNT(*) FROM aarch64_sysreg_fields").fetchone()[0],
    }

    print(f"Database Statistics:")
    print(f"  Unique Registers: {stats['total_registers']}")
    print(f"  Unique Features:  {stats['total_features']}")
    print(f"  Total Fields:     {stats['total_fields']}")
    print()

    # Strategy: Create one document per register with complete information
    # This provides semantically complete chunks for RAG

    # Get all registers with their features and fields
    query = """
        SELECT
            r.register_name,
            STRING_AGG(DISTINCT r.feature_name, ', ') as features,
            MAX(r.long_name) as long_name,
            MAX(r.register_width) as register_width,
            MAX(r.reg_purpose) as reg_purpose,
            COUNT(DISTINCT f.field_name) as field_count
        FROM aarch64_sysreg r
        LEFT JOIN aarch64_sysreg_fields f ON r.register_name = f.register_name
        GROUP BY r.register_name
        ORDER BY r.register_name
    """

    registers = conn.execute(query).fetchall()

    # Get all fields
    fields_query = """
        SELECT
            register_name,
            field_name,
            field_msb,
            field_lsb,
            field_position,
            field_width,
            field_description,
            field_definition
        FROM aarch64_sysreg_fields
        ORDER BY register_name, field_msb DESC
    """

    fields = conn.execute(fields_query).fetchall()

    # Group fields by register
    fields_by_register = {}
    for field in fields:
        reg_name = field[0]
        if reg_name not in fields_by_register:
            fields_by_register[reg_name] = []
        fields_by_register[reg_name].append(field)

    conn.close()

    # Write JSONL file
    print(f"Generating JSONL for {len(registers)} registers...")

    documents = []

    for idx, reg in enumerate(registers, 1):
        reg_name, features, long_name, width, purpose, field_count = reg

        # Build comprehensive text content for embedding
        text_parts = []

        # Register overview
        text_parts.append(f"Register: {reg_name}")
        if long_name and long_name != 'None':
            text_parts.append(f"Full Name: {clean_text(long_name)}")

        text_parts.append(f"Width: {width} bits")

        if features:
            text_parts.append(f"Required Features: {features}")

        if purpose and purpose != 'None':
            text_parts.append(f"Purpose: {clean_text(purpose)}")

        # Add field information
        if reg_name in fields_by_register:
            text_parts.append(f"\nFields ({len(fields_by_register[reg_name])} total):")

            for field in fields_by_register[reg_name]:
                (_, field_name, msb, lsb, position,
                 field_width, description, definition) = field

                field_info = f"  - {field_name} {position}: {field_width} bits"
                if definition:
                    field_info += f" [{definition}]"
                if description and description != 'None':
                    field_info += f" - {clean_text(description)[:200]}"

                text_parts.append(field_info)

        text_content = "\n".join(text_parts)

        # Build metadata (FLAT structure - no nesting!)
        # Handle register_width which may contain comma-separated values
        width_str = str(width) if width else "64"
        # Take first value if comma-separated (e.g., "25,64,24" -> "64")
        if ',' in width_str:
            width_parts = width_str.split(',')
            # Usually the middle or max value is most representative
            width_str = max(width_parts, key=lambda x: int(x.strip()) if x.strip().isdigit() else 0)

        metadata = {
            "register_name": reg_name,
            "register_width": int(width_str) if width_str.isdigit() else 64,
            "long_name": clean_text(long_name),
            "features": features if features else "",
            "purpose": clean_text(purpose)[:500] if purpose else "",  # Truncate long text
            "field_count": int(field_count),
            "architecture": "AArch64",
            "spec_version": "2025-09",
            "doc_type": "system_register",
            "has_fields": len(fields_by_register.get(reg_name, [])) > 0,
        }

        # Create document object (LlamaIndex format)
        document = {
            "id": generate_id(reg_name),
            "text": text_content,
            "metadata": metadata
        }

        documents.append(document)

        # Progress indicator
        if idx % 100 == 0:
            print(f"  Processed {idx}/{len(registers)} registers...")

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
