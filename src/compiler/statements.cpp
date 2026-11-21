#include "plusminus/compiler.hpp"
#include <stdexcept>
#include <string>
#include <utility>

void Compiler::parseProgram() {
    while (true) {
        skipWs();
        if (atEnd()) break;
        if (checkKeyword("func")) { consumeKeyword("func"); parseFunctionDef(false); continue; }
        if (checkKeyword("proc")) { consumeKeyword("proc"); parseFunctionDef(true); continue; }
        parseStatement();
    }
}

void Compiler::parseFunctionDef(bool isProc) {
    skipWs();
    if (checkKeyword("int")) { consumeKeyword("int"); skipWs(); }
    else if (checkKeyword("float")) { consumeKeyword("float"); skipWs(); }
    else if (checkKeyword("double")) { consumeKeyword("double"); skipWs(); }

    std::string name = parseIdentifier();
    expect('(');
    std::vector<std::string> params;
    skipWs();
    if (peek() != ')') {
        params.push_back(parseIdentifier());
        skipWs();
        while (peek() == ',') {
            advance(); skipWs(); params.push_back(parseIdentifier()); skipWs();
        }
    }
    expect(')');

    Command def;
    def.op = isProc ? OpCode::ProcDef : OpCode::FuncDef;
    def.name = name;
    def.params = params;
    emit(def);
    size_t defPos = program.size() - 1;

    emit(OpCode::Jmp);
    size_t jmpPos = program.size() - 1;

    program[defPos].target = (int)program.size();
    parseBlock();

    Command ret;
    ret.op = OpCode::Return;
    ret.num = 0.0;
    emit(ret);

    program[jmpPos].target = (int)program.size();
}

void Compiler::parseStatement() {
    skipWs();
    if (atEnd()) return;

    if (checkKeyword("return")) {
        consumeKeyword("return"); skipWs();
        if (peek() == ';') { advance(); Command c; c.op = OpCode::Return; c.num = 0.0; emit(c); }
        else { parseExpr(); skipWs(); if (peek() == ';') advance(); emit(OpCode::Return); }
        return;
    }

    if (checkKeyword("go")) {
        consumeKeyword("go"); skipWs();
        std::string name = parseIdentifier();
        expect('(');
        int argc = 0; skipWs();
        if (peek() != ')') {
            parseExpr(); argc++; skipWs();
            while (peek() == ',') { advance(); parseExpr(); argc++; skipWs(); }
        }
        expect(')'); skipWs();
        if (peek() == ';') advance();
        Command c; c.op = OpCode::GoCall; c.name = name; c.argc = argc;
        emit(c); return;
    }

    if (checkKeyword("sync")) {
        consumeKeyword("sync"); skipWs();
        if (peek() == ';') advance();
        emit(OpCode::Sync); return;
    }

    if (checkKeyword("lock")) {
        consumeKeyword("lock"); expect('(');
        std::string var = parseIdentifier(); expect(')'); skipWs();
        if (peek() == ';') advance();
        Command c; c.op = OpCode::Lock; c.name = var; emit(c); return;
    }

    if (checkKeyword("unlock")) {
        consumeKeyword("unlock"); expect('(');
        std::string var = parseIdentifier(); expect(')'); skipWs();
        if (peek() == ';') advance();
        Command c; c.op = OpCode::Unlock; c.name = var; emit(c); return;
    }

    if (checkKeyword("int")) { consumeKeyword("int"); skipWs(); }
    else if (checkKeyword("float")) { consumeKeyword("float"); skipWs(); }
    else if (checkKeyword("double")) { consumeKeyword("double"); skipWs(); }

    if (checkKeyword("if")) { consumeKeyword("if"); parseIf(); return; }
    if (checkKeyword("while")) { consumeKeyword("while"); parseWhile(); return; }
    if (peek() == '{') { parseBlock(); return; }

    if (std::isalpha(static_cast<unsigned char>(peek())) || peek() == '_') {
        size_t save = pos;
        std::string name = parseIdentifier();
        skipWs();

        if (peek() == '[') {
            advance();
            size_t progSizeBeforeIndex = program.size();
            parseExpr();
            expect(']');
            skipWs();

            if (peek() == ';') {
                advance(); emit(OpCode::MakeArraySized);
                Command c; c.op = OpCode::Store; c.name = name; emit(c); return;
            }

            if (peek() == '=' && peek2() != '=') {
                advance();
                std::vector<Command> indexCmds(program.begin() + progSizeBeforeIndex, program.end());
                program.resize(progSizeBeforeIndex);
                Command c; c.op = OpCode::PushVar; c.name = name; emit(c);
                program.insert(program.end(), indexCmds.begin(), indexCmds.end());
                parseExpr(); skipWs();
                if (peek() == ';') advance();
                emit(OpCode::StoreIndex); return;
            }

            program.resize(progSizeBeforeIndex);
            pos = save;
        }
        else if (peek() == '=' && peek2() != '=') {
            advance(); skipWs();

            if (peek() == '[') {
                advance();
                int count = 0; skipWs();
                if (peek() != ']') {
                    parseExpr(); count++; skipWs();
                    while (peek() == ',') { advance(); parseExpr(); count++; skipWs(); }
                }
                expect(']'); expect(';');
                Command c; c.op = OpCode::MakeArray; c.argc = count; emit(c);
                Command s; s.op = OpCode::Store; s.name = name; emit(s); return;
            }

            parseExpr(); skipWs();
            Command c; c.op = OpCode::Store; c.name = name; emit(c);

            while (peek() == ',') {
                advance(); skipWs();
                std::string nextName = parseIdentifier(); skipWs();
                expect('='); skipWs();
                parseExpr(); skipWs();
                Command c2; c2.op = OpCode::Store; c2.name = nextName; emit(c2);
            }

            if (peek() == ';') advance();
            return;
        }
        else {
            pos = save;
        }
    }

    parseExpr(); skipWs();
    if (peek() == ';') { advance(); emit(OpCode::Pop); }
}

void Compiler::parseBlock() {
    expect('{');
    while (true) {
        skipWs();
        if (peek() == '}') { advance(); return; }
        if (atEnd()) throw std::runtime_error("Expected '}'");
        parseStatement();
    }
}

void Compiler::parseIf() {
    skipWs();
    if (peek() == '(') { advance(); parseExpr(); expect(')'); }
    else { parseExpr(); }

    emit(OpCode::Jz);
    size_t jzPos = program.size() - 1;
    parseStatement();
    if (checkKeyword("else")) {
        consumeKeyword("else");
        emit(OpCode::Jmp);
        size_t jmpPos = program.size() - 1;
        program[jzPos].target = (int)program.size();
        parseStatement();
        program[jmpPos].target = (int)program.size();
    }
    else { program[jzPos].target = (int)program.size(); }
}

void Compiler::parseWhile() {
    size_t loopStart = (size_t)program.size();
    skipWs();
    if (peek() == '(') { advance(); parseExpr(); expect(')'); }
    else { parseExpr(); }

    emit(OpCode::Jz);
    size_t jzPos = program.size() - 1;
    parseStatement();
    emit(OpCode::Jmp);
    program.back().target = (int)loopStart;
    program[jzPos].target = (int)program.size();
}
