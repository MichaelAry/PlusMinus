#pragma once
#include "plusminus/bytecode.hpp"
#include <string>
#include <unordered_map>
#include <vector>

bool isExpression(const std::string& input);
std::vector<Command> compileToCommands(const std::string& input);
double evaluate(const std::string& input);
std::unordered_map<std::string, double> runAndGetVars(const std::string& input);
std::vector<double> getArrayVar(const std::string& input, const std::string& varName);
std::string getOutput(const std::string& input);
