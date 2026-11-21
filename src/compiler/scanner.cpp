#include "plusminus/compiler.hpp"
#include <cctype>
#include <stdexcept>
#include <string>

bool Compiler::atEnd() const { return pos >= src.size(); }
char Compiler::peek()  const { return atEnd() ? '\0' : src[pos]; }
char Compiler::peek2() const { return (pos + 1 < src.size()) ? src[pos + 1] : '\0'; }
void Compiler::advance() { ++pos; }

void Compiler::skipWs() {
    while (!atEnd()) {
        if (std::isspace(static_cast<unsigned char>(peek()))) { advance(); continue; }
        if (peek() == '/' && peek2() == '/') {
            advance(); advance();
            while (!atEnd() && peek() != '\n') advance();
            continue;
        }
        if (peek() == '/' && peek2() == '*') {
            advance(); advance();
            bool closed = false;
            while (!atEnd()) {
                if (peek() == '*' && peek2() == '/') { advance(); advance(); closed = true; break; }
                advance();
            }
            if (!closed) throw std::runtime_error("Unclosed multi-line comment");
            continue;
        }
        break;
    }
}

bool Compiler::eatAnd() {
    skipWs();
    if (peek() == '&' && peek2() == '&') { pos += 2; return true; }
    return false;
}

void Compiler::expect(char c) {
    skipWs();
    if (peek() != c) throw std::runtime_error(std::string("Expected '") + c + "'");
    advance();
}

bool Compiler::checkKeyword(const std::string& kw) {
    skipWs();
    if (pos + kw.size() > src.size()) return false;
    if (src.compare(pos, kw.size(), kw) != 0) return false;
    size_t end = pos + kw.size();
    if (end < src.size()) {
        char c = src[end];
        if (std::isalnum(static_cast<unsigned char>(c)) || c == '_') return false;
    }
    return true;
}

void Compiler::consumeKeyword(const std::string& kw) {
    if (!checkKeyword(kw)) throw std::runtime_error("Expected keyword: " + kw);
    pos += kw.size();
}

double Compiler::parseNumber() {
    size_t start = pos;
    while (!atEnd() && std::isdigit(static_cast<unsigned char>(peek()))) advance();
    if (!atEnd() && peek() == '.') {
        advance();
        while (!atEnd() && std::isdigit(static_cast<unsigned char>(peek()))) advance();
    }
    return std::stod(std::string(src.substr(start, pos - start)));
}

std::string Compiler::parseIdentifier() {
    size_t start = pos;
    while (!atEnd() && (std::isalnum(static_cast<unsigned char>(peek())) || peek() == '_')) advance();
    return std::string(src.substr(start, pos - start));
}
