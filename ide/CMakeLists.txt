# Compatibility entry point for existing scripts invoking cmake -S ide.
cmake_minimum_required(VERSION 3.16)
project(PlusMinusIDE LANGUAGES CXX)
add_subdirectory(.. "${CMAKE_CURRENT_BINARY_DIR}/plusminus-root")
