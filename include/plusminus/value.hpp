#pragma once
#include <complex>
#include <memory>
#include <string>
#include <vector>
#include <utility>

struct Value {
    double num = 0.0;
    std::shared_ptr<std::vector<double>> arr;
    std::string str;
    bool isStr = false;

    // Complex values live beside the original real/array/string payload so
    // existing programs keep their exact semantics. Arithmetic promotion is
    // implemented in the Math library (plusminus/math.hpp).
    std::complex<double> z{};
    bool isCplx = false;

    bool isArray() const { return arr != nullptr; }
    bool isString() const { return isStr; }
    bool isComplex() const { return isCplx; }

    Value() : num(0.0) {}
    Value(double v) : num(v) {}
    Value(std::shared_ptr<std::vector<double>> a) : num(0.0), arr(a) {}
    Value(const std::string& s) : str(s), isStr(true) {}
    Value(const std::complex<double>& value) : z(value), isCplx(true) {}

    double getNum() const { return isCplx ? z.real() : num; }
    double getRe() const { return isCplx ? z.real() : num; }
    double getIm() const { return isCplx ? z.imag() : 0.0; }
    std::complex<double> getComplex() const {
        return isCplx ? z : std::complex<double>(num, 0.0);
    }
    std::shared_ptr<std::vector<double>> getArr() const { return arr; }
};
