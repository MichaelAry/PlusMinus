#include "builtins.hpp"
#include <cmath>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

bool executeBuiltin(const Command& c, std::vector<Value>& stack,
                    std::string& output, std::mutex& outputMutex) {
    auto popNum = [&]() {
        if (stack.empty()) throw std::runtime_error("Stack underflow");
        Value v = stack.back(); stack.pop_back();
        if (v.isArray()) throw std::runtime_error("Expected number, got array");
        return v.getNum();
    };
            if (c.name == "print") {
                std::vector<Value> args(c.argc);
                for (int i = c.argc - 1; i >= 0; --i) {
                    if (stack.empty()) throw std::runtime_error("Stack underflow in print");
                    args[i] = stack.back(); stack.pop_back();
                }
                std::ostringstream oss;
                for (size_t i = 0; i < args.size(); ++i) {
                    const Value& arg = args[i];
                    if (arg.isString()) oss << arg.str;
                    else if (arg.isArray()) {
                        oss << "[";
                        for (size_t j = 0; j < arg.getArr()->size(); ++j) {
                            oss << arg.getArr()->at(j);
                            if (j + 1 < arg.getArr()->size()) oss << ", ";
                        }
                        oss << "]";
                    }
                    else oss << arg.getNum();
                    if (i + 1 < args.size()) {
                        if (!arg.isString() || arg.str.empty() || arg.str.back() != ' ') oss << " ";
                    }
                }
                {
                    std::lock_guard<std::mutex> lock(outputMutex);
                    output += oss.str() + "\n";
                }
                stack.push_back(Value(0.0));
            }
            else if (c.name == "resize") {
                if (c.argc != 2) throw std::runtime_error("resize expects 2 args");
                double newSize = popNum();
                Value arrVal = stack.back(); stack.pop_back();
                if (!arrVal.isArray()) throw std::runtime_error("resize expects an array");
                arrVal.getArr()->resize((size_t)newSize, 0.0);
                stack.push_back(Value(0.0));
            }
            else if (c.name == "len") {
                if (c.argc != 1) throw std::runtime_error("len expects 1 arg");
                if (stack.empty()) throw std::runtime_error("Stack underflow in len");
                Value arg = stack.back(); stack.pop_back();
                if (!arg.isArray()) throw std::runtime_error("len expects an array");
                stack.push_back(Value(static_cast<double>(arg.getArr()->size())));
            }
            else if (c.name == "sin") {
                if (c.argc != 1) throw std::runtime_error("sin expects 1 arg");
                stack.push_back(Value(std::sin(popNum())));
            }
            else if (c.name == "cos") {
                if (c.argc != 1) throw std::runtime_error("cos expects 1 arg");
                stack.push_back(Value(std::cos(popNum())));
            }
            else if (c.name == "pow") {
                if (c.argc != 2) throw std::runtime_error("pow expects 2 args");
                double exp = popNum();
                double base = popNum();
                stack.push_back(Value(std::pow(base, exp)));
            }
            else if (c.name == "fact") {
                if (c.argc != 1) throw std::runtime_error("fact expects 1 arg");
                double val = popNum();
                if (val < 0 || val != std::floor(val)) throw std::runtime_error("Factorial expects non-negative integer");
                double res = 1.0;
                for (int i = 2; i <= (int)val; ++i) res *= i;
                stack.push_back(Value(res));
            }
            else if (c.name == "multifact") {
                if (c.argc != 2) throw std::runtime_error("multifact expects 2 args");
                double step = popNum();
                double val = popNum();
                if (val < 0 || val != std::floor(val) || step < 1) throw std::runtime_error("Invalid args for multifact");
                double res = 1.0;
                for (double i = val; i > 0; i -= step) res *= i;
                stack.push_back(Value(res));
            }
    else {
        return false;
    }
    return true;
}
