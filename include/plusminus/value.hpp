#pragma once
#include <memory>
#include <string>
#include <vector>
#include <utility>

struct Value {
    double num = 0.0;
    std::shared_ptr<std::vector<double>> arr;
    std::string str;
    bool isStr = false;

    bool isArray() const { return arr != nullptr; }
    bool isString() const { return isStr; }

    Value() : num(0.0) {}
    Value(double v) : num(v) {}
    Value(std::shared_ptr<std::vector<double>> a) : num(0.0), arr(a) {}
    Value(const std::string& s) : str(s), isStr(true) {}

    double getNum() const { return num; }
    std::shared_ptr<std::vector<double>> getArr() const { return arr; }
};
