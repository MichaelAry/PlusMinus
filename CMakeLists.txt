cmake_minimum_required(VERSION 3.16)
project(PlusMinus VERSION 2.0 LANGUAGES CXX)

find_package(Threads REQUIRED)
include(CTest)

add_library(plusminus_core STATIC
    src/compiler/compiler.cpp
    src/compiler/scanner.cpp
    src/compiler/statements.cpp
    src/compiler/expressions.cpp
    src/vm/vm.cpp
    src/vm/executor.cpp
    src/api.cpp
)
target_compile_features(plusminus_core PUBLIC cxx_std_20)
target_include_directories(plusminus_core PUBLIC
    "${CMAKE_CURRENT_SOURCE_DIR}/include"
    "${CMAKE_CURRENT_SOURCE_DIR}" # Temporary compatibility include for Parser.h
)
target_link_libraries(plusminus_core PUBLIC Threads::Threads)

if(MSVC)
    target_compile_options(plusminus_core PRIVATE /W4 /utf-8)
else()
    target_compile_options(plusminus_core PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_executable(plusminus_runner ide/runner.cpp)
target_link_libraries(plusminus_runner PRIVATE plusminus_core)
set_target_properties(plusminus_runner PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
)

if(BUILD_TESTING)
    add_executable(plusminus_core_smoke tests/cpp/core_smoke.cpp)
    target_link_libraries(plusminus_core_smoke PRIVATE plusminus_core)
    add_test(NAME core_smoke COMMAND plusminus_core_smoke)
endif()
