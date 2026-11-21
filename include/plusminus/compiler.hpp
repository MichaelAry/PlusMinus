#pragma once
#include "plusminus/bytecode.hpp"
#include <cstddef>
#include <string>
#include <stdexcept>
#include <string_view>
#include <vector>

// Structured compile errors retain the parser's source coordinate.
struct CompileError : std::runtime_error {
    std::size_t offset, line, column;
    CompileError(const std::string& message, std::size_t off,
                 std::size_t ln, std::size_t col)
        : std::runtime_error(message), offset(off), line(ln), column(col) {}
};

class Compiler {
public:
    Compiler(std::string_view input);
    std::vector<Command> compile();

private:
    std::string_view src;
    size_t pos = 0;
    std::vector<Command> program;

    bool atEnd() const;
    char peek() const;
    char peek2() const;
    void advance();
    void skipWs();
    bool eatAnd();
    void expect(char c);
    bool checkKeyword(const std::string& kw);
    void consumeKeyword(const std::string& kw);
    void emit(Command c);
    void emit(OpCode op);

    void parseProgram();
    void parseStatement();
    void parseBlock();
    void parseIf();
    void parseWhile();
    void parseFunctionDef(bool isProc);
    void parseExpr();
    void parseCompare();
    void parseSum();
    void parseTerm();
    void parseFactor();
    void parseOperand();
    double parseNumber();
    std::string parseIdentifier();
};
