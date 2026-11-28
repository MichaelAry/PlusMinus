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
    src/vm/builtins.cpp
    src/vm/mathlib.cpp
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

    # Drawer/Math coverage is a standalone smoke test so the original 225
    # generated TEST_METHOD adapters keep their documented count.
    add_executable(plusminus_drawer_smoke tests/cpp/drawer_smoke.cpp)
    target_link_libraries(plusminus_drawer_smoke PRIVATE plusminus_core)
    add_test(NAME drawer_smoke COMMAND plusminus_drawer_smoke)
endif()

# Full original C++ test suite: generated cross-platform registration adapters.
if(BUILD_TESTING)
    find_package(Python3 COMPONENTS Interpreter QUIET)
    if(Python3_Interpreter_FOUND)
        set(PM_GENERATED_NATIVE "${CMAKE_CURRENT_BINARY_DIR}/generated-native")
        set(PM_TEST_GROUPS arithmetic control_flow bytecode arrays builtins concurrency functions)
        set(PM_WRAPPERS)
        set(PM_TEST_FILES)
        foreach(group IN LISTS PM_TEST_GROUPS)
            list(APPEND PM_WRAPPERS "${PM_GENERATED_NATIVE}/${group}_tests_registration.cpp")
            list(APPEND PM_TEST_FILES "${CMAKE_CURRENT_SOURCE_DIR}/tests/cpp/${group}_tests.cpp")
        endforeach()
        add_custom_command(
            OUTPUT ${PM_WRAPPERS}
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/generate_native_tests.py"
                    "${CMAKE_CURRENT_SOURCE_DIR}" "${PM_GENERATED_NATIVE}"
            DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/tools/generate_native_tests.py" ${PM_TEST_FILES}
            COMMENT "Registering 225 native PlusMinus tests"
            VERBATIM
        )
        add_executable(plusminus_native_tests tests/portable/main.cpp ${PM_WRAPPERS})
        target_include_directories(plusminus_native_tests PRIVATE
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/portable" "${CMAKE_CURRENT_SOURCE_DIR}")
        target_link_libraries(plusminus_native_tests PRIVATE plusminus_core)
        add_test(NAME native_quick COMMAND plusminus_native_tests --suite quick)
        set_tests_properties(native_quick PROPERTIES TIMEOUT 150)
    endif()
endif()
