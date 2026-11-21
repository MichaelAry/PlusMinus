#include "plusminus/api.hpp"
#include "plusminus/compiler.hpp"
#include "plusminus/vm.hpp"
#include <string>
#include <unordered_map>
#include <vector>

bool isExpression(const std::string& input) {
    try { Compiler c(input); (void)c.compile(); return true; }
    catch (...) { return false; }
}

std::vector<Command> compileToCommands(const std::string& input) {
    Compiler c(input); return c.compile();
}

double evaluate(const std::string& input) {
    Compiler c(input); auto p = c.compile(); VM vm; return vm.run(p);
}

std::unordered_map<std::string, double> runAndGetVars(const std::string& input) {
    Compiler c(input); auto p = c.compile(); VM vm; vm.run(p);
    std::unordered_map<std::string, double> result;
    for (auto& [k, v] : vm.vars) {
        if (!v.isArray()) result[k] = v.getNum();
    }
    return result;
}

std::vector<double> getArrayVar(const std::string& input, const std::string& varName) {
    Compiler c(input); auto p = c.compile(); VM vm; vm.run(p);
    auto it = vm.vars.find(varName);
    if (it != vm.vars.end() && it->second.isArray()) return *(it->second.getArr());
    return {};
}

std::string getOutput(const std::string& input) {
    Compiler c(input);
    auto p = c.compile();
    VM vm;
    vm.run(p);
    return vm.output;
}
