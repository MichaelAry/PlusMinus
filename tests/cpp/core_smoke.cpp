#include "plusminus/api.hpp"
#include <cmath>
#include <exception>
#include <iostream>
#include <string>

int main() {
    try {
        if (std::abs(evaluate("2 + 3 * 4") - 14.0) > 1e-12) return 1;
        if (getOutput("x = 10; print(x);") != "10\n") return 2;
        if (std::abs(evaluate("pow(2, 3)") - 8.0) > 1e-12) return 3;
        if (isExpression("if (1) {")) return 4;
        if (compileToCommands("x = 1;").empty()) return 5;
        std::cout << "PlusMinus core smoke: OK\n";
        return 0;
    } catch (const std::exception& ex) {
        std::cerr << "PlusMinus core smoke failed: " << ex.what() << '\n';
        return 10;
    }
}
