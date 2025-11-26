cmake_minimum_required(VERSION 3.10)
project(query_isa)

# Set C++ standard
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Compiler flags
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra")
set(CMAKE_CXX_FLAGS_RELEASE "-O3")
set(CMAKE_CXX_FLAGS_DEBUG "-O0 -g")

# Default to Release build if not specified
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Python executable for generating encoding data
find_program(PYTHON_EXECUTABLE python3)

# Generated files
set(ENCODING_HEADER "${CMAKE_CURRENT_SOURCE_DIR}/encoding_data.h")
set(ENCODING_SOURCES "")
foreach(i RANGE 0 9)
    list(APPEND ENCODING_SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/encoding_data_${i}.cpp")
endforeach()

# Custom command to generate encoding data files
add_custom_command(
    OUTPUT ${ENCODING_HEADER} ${ENCODING_SOURCES}
    COMMAND ${PYTHON_EXECUTABLE} gen_encoding_data.py
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    DEPENDS gen_encoding_data.py
    COMMENT "Generating encoding data files..."
)

# Main executable
add_executable(query_isa
    query_isa.cpp
    ${ENCODING_SOURCES}
)

# Ensure header is generated before compiling
add_custom_target(generate_encoding_data DEPENDS ${ENCODING_HEADER} ${ENCODING_SOURCES})
add_dependencies(query_isa generate_encoding_data)

# Install target
install(TARGETS query_isa DESTINATION ${CMAKE_CURRENT_SOURCE_DIR}/..)

# query_register (v2 - uses pre-generated static data, no DuckDB dependency)
set(REGISTER_DATA_HEADER "${CMAKE_CURRENT_SOURCE_DIR}/register_data.h")
set(REGISTER_DATA_SOURCES "")
list(APPEND REGISTER_DATA_SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/register_data.cpp")
foreach(i RANGE 0 4)
    list(APPEND REGISTER_DATA_SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/register_data_${i}.cpp")
endforeach()

# Custom command to generate register data files
add_custom_command(
    OUTPUT ${REGISTER_DATA_HEADER} ${REGISTER_DATA_SOURCES}
    COMMAND ${PYTHON_EXECUTABLE} gen_register_data.py
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    DEPENDS gen_register_data.py
    COMMENT "Generating register data files..."
)

# Register query executable
add_executable(query_register
    query_register.cpp
    ${REGISTER_DATA_SOURCES}
)

# Ensure header is generated before compiling
add_custom_target(generate_register_data DEPENDS ${REGISTER_DATA_HEADER} ${REGISTER_DATA_SOURCES})
add_dependencies(query_register generate_register_data)

install(TARGETS query_register DESTINATION ${CMAKE_CURRENT_SOURCE_DIR}/..)

# Test target
enable_testing()
add_test(NAME test_0x91000000 COMMAND query_isa --op 0x91000000)
add_test(NAME test_0x910083e0 COMMAND query_isa --op 0x910083e0)
add_test(NAME test_0xd503201f COMMAND query_isa --op 0xd503201f)
add_test(NAME test_separator COMMAND query_isa --op 0x91_00_00_00)

# Clean target for generated files
add_custom_target(clean-generated
    COMMAND ${CMAKE_COMMAND} -E remove ${ENCODING_HEADER} ${ENCODING_SOURCES}
    COMMENT "Removing generated encoding data files..."
)
