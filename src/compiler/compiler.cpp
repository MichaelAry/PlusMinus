#include "plusminus/compiler.hpp"
#include <utility>

Compiler::Compiler(std::string_view input) : src(input) {}

void Compiler::emit(Command c) { program.push_back(std::move(c)); }
void Compiler::emit(OpCode op) { program.push_back(Command{ op }); }

std::vector<Command> Compiler::compile() {
    parseProgram();
    emit(OpCode::Halt);
    return std::move(program);
}
