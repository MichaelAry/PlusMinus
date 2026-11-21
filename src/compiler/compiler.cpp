#include "plusminus/compiler.hpp"
#include <utility>

Compiler::Compiler(std::string_view input) : src(input) {}

void Compiler::emit(Command c) { program.push_back(std::move(c)); }
void Compiler::emit(OpCode op) { program.push_back(Command{ op }); }

std::vector<Command> Compiler::compile() {
    try {
        parseProgram();
        emit(OpCode::Halt);
        return std::move(program);
    } catch (const std::exception& exc) {
        std::size_t line = 1, column = 1;
        for (std::size_t i = 0; i < pos && i < src.size(); ++i) {
            if (src[i] == '\n') { ++line; column = 1; }
            else { ++column; }
        }
        throw CompileError(exc.what(), pos, line, column);
    }
}
