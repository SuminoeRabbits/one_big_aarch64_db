# query_isa, faster and portable aarch64 binary disassembler

This guide assumes source generation and compilation may occur on different machines (e.g., x86-64 host for database generation, AArch64 target for compilation).

## Why you need query_isa?
A query_isa is native C++ implemenaiton of `python3 ./query_isa.py --op`. You can easily disassemble aarch64 binary into arm assembler syntax in line-by-line with using this query_isa, which is faster, portable on various machine, and easy to call from other native applications without python/duckdb support.

## Step 1: Generate Encoding Data (on host with database)

Generate the encoding source files from the database:

```bash
cd cpp_source
python3 gen_encoding_data.py
```

**Generated files:**
- `encoding_data.h` - Header with structure definitions
- `encoding_data_0.cpp` through `encoding_data_9.cpp` - Split encoding data (10 files, ~465 encodings each)

**Note:** These generated files are architecture-independent and can be transferred to any build machine.

## Step 2: Transfer Files (if building on different machine)

If building on a remote machine, transfer the entire `cpp_source/` directory:

```bash
# Example: Transfer to AArch64 remote machine
scp -r cpp_source/ user@aarch64-host:/path/to/build/
```

**Required files for building:**
- `query_isa.cpp`
- `encoding_data.h` (generated in Step 1)
- `encoding_data_*.cpp` (10 files, generated in Step 1)
- `CMakeLists.txt`

## Step 3: Build (on target machine)

On the build machine (e.g., AArch64 Linux):

```bash
cd cpp_source
cmake -B build
cmake --build build -j$(nproc)
cmake --install build
```

The binary will be installed to the parent directory as `../query_isa`.

## Build Options

```bash
# Release build (default, -O3 optimization)
cmake -B build -DCMAKE_BUILD_TYPE=Release

# Debug build (-O0, no optimization)
cmake -B build -DCMAKE_BUILD_TYPE=Debug
```

## Testing

```bash
cd build
ctest
```

## Usage

After building, the `query_isa` binary will be installed to the parent directory:

```bash
# Decode opcode to ARM assembly
./query_isa --op 0x91000000
./query_isa --op 0x910083e0
./query_isa --op 0xd503201f

# With separators for readability
./query_isa --op 0x91_00_00_00

# Show help
./query_isa --help
```

**Example output:**

```bash
$ ./query_isa --op 0x91000000
ADD x0, x0, #0x0
MOV x0, x0

$ ./query_isa --op 0x910083e0
ADD x0, sp, #0x20

$ ./query_isa --op 0xd503201f
AUTIB1716
PACIB1716
PACIA1716
AUTIA1716
NOP
HINT #0x0
```

## Clean

```bash
# Clean build artifacts only
cmake --build build --target clean

# Remove entire build directory
rm -rf build

# Clean generated encoding data files (requires database access)
rm -f encoding_data.h encoding_data_*.cpp
```

## Notes

- **Source generation requires:** Python 3 + DuckDB, access to `../aarch64_isa_db.duckdb`
- **Build requires:** CMake 3.10+, C++11 compiler, no external dependencies
- **Build time:** ~1m47s with parallel compilation on multi-core systems
- **Cross-compilation:** Generated encoding files are architecture-independent; only `query_isa.cpp` needs compilation for the target architecture
