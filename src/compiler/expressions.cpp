#include "plusminus/compiler.hpp"
#include <cmath>
#include <stdexcept>
#include <string>

void Compiler::parseExpr() {
    parseCompare(); skipWs();
    while (eatAnd()) { parseCompare(); emit(OpCode::And); skipWs(); }
}

void Compiler::parseCompare() {
    parseSum(); skipWs();
    while (peek() == '<' || peek() == '>') {
        char op = peek(); advance(); parseSum();
        emit(op == '<' ? OpCode::Less : OpCode::Greater); skipWs();
    }
}

void Compiler::parseSum() {
    parseTerm(); skipWs();
    while (peek() == '+' || peek() == '-') {
        char op = peek(); advance(); parseTerm();
        emit(op == '+' ? OpCode::Add : OpCode::Sub); skipWs();
    }
}

void Compiler::parseTerm() {
    parseFactor(); skipWs();
    while (peek() == '*' || peek() == '/' || peek() == '%') {
        char op = peek(); advance(); parseFactor();
        if (op == '*') emit(OpCode::Mul);
        else if (op == '/') emit(OpCode::Div);
        else emit(OpCode::Mod);
        skipWs();
    }
}

void Compiler::parseFactor() {
    skipWs();
    if (peek() == '-' || peek() == '+') {
        char op = peek(); advance();
        if (op == '-') { Command c; c.op = OpCode::PushConst; c.num = 0.0; emit(c); parseFactor(); emit(OpCode::Sub); }
        else { parseFactor(); }
        return;
    }

    parseOperand(); skipWs();
    int bangs = 0;
    while (peek() == '!') { advance(); bangs++; skipWs(); }

    if (bangs == 1) { Command c; c.op = OpCode::Call; c.name = "fact"; c.argc = 1; emit(c); }
    else if (bangs > 1) {
        Command k; k.op = OpCode::PushConst; k.num = bangs; emit(k);
        Command c; c.op = OpCode::Call; c.name = "multifact"; c.argc = 2; emit(c);
    }

    if (peek() == '^') { advance(); parseFactor(); emit(OpCode::Pow); }
}

void Compiler::parseOperand() {
    skipWs();

    // --- ДОБАВЛЕНО: Поддержка строковых литералов ---
    if (peek() == '"') {
        advance();
        std::string s;
        while (!atEnd() && peek() != '"') {
            s += peek();
            advance();
        }
        expect('"');
        Command c; c.op = OpCode::PushConst; c.str = s; c.isStr = true; emit(c); return;
    }
    // ----------------------------------------------

    if (std::isdigit(static_cast<unsigned char>(peek()))) {
        Command c; c.op = OpCode::PushConst; c.num = parseNumber(); emit(c); return;
    }
    if (std::isalpha(static_cast<unsigned char>(peek())) || peek() == '_') {
        std::string name = parseIdentifier(); skipWs();
        if (peek() == '[') {
            advance(); Command c; c.op = OpCode::PushVar; c.name = name; emit(c);
            parseExpr(); expect(']'); emit(OpCode::LoadIndex); return;
        }
        if (peek() == '(') {
            advance(); int argc = 0; skipWs();
            if (peek() != ')') {
                parseExpr(); argc++; skipWs();
                while (peek() == ',') { advance(); parseExpr(); argc++; skipWs(); }
            }
            expect(')');
            Command c; c.op = OpCode::Call; c.name = name; c.argc = argc; emit(c); return;
        }
        Command c; c.op = OpCode::PushVar; c.name = name; emit(c); return;
    }
    if (peek() == '(') { advance(); parseExpr(); expect(')'); return; }
    throw std::runtime_error("Expected operand");
}
