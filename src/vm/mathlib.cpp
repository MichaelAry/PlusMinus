#include "plusminus/math.hpp"
#include <cmath>
#include <complex>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <vector>

namespace plusminus::math {
namespace {

using Complex = std::complex<double>;

[[noreturn]] void typeError(const std::string& name, const Value& value) {
    if (value.isArray()) throw std::runtime_error(name + " expects a number, got an array");
    if (value.isString()) throw std::runtime_error(name + " expects a number, got a string");
    throw std::runtime_error(name + " expects a number");
}

double asReal(const Value& value, const std::string& name) {
    if (value.isComplex()) throw std::runtime_error(name + " expects a real number, got a complex number");
    if (value.isArray() || value.isString()) typeError(name, value);
    return value.getNum();
}

Complex asComplex(const Value& value, const std::string& name) {
    if (value.isArray() || value.isString()) typeError(name, value);
    return value.getComplex();
}

Value popValue(std::vector<Value>& stack) {
    if (stack.empty()) throw std::runtime_error("Stack underflow");
    Value value = stack.back();
    stack.pop_back();
    return value;
}

double popReal(std::vector<Value>& stack, const std::string& name) {
    return asReal(popValue(stack), name);
}

Complex popComplex(std::vector<Value>& stack, const std::string& name) {
    return asComplex(popValue(stack), name);
}

void requireArgs(const std::string& name, std::size_t got, std::size_t want) {
    if (got != want)
        throw std::runtime_error(name + " expects " + std::to_string(want) + " argument(s)");
}

bool isOwnedName(const std::string& name) {
    static const std::unordered_set<std::string> names = {
        "complex", "cplx", "re", "real", "im", "imag", "conj", "arg", "cabs",
        "cadd", "csub", "cmul", "cdiv",
        "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
        "sqrt", "cbrt", "exp", "log", "log10", "floor", "ceil", "round",
        "abs", "sign", "min", "max", "hypot", "clamp", "lerp", "deg", "rad",
        "pow", "fact", "multifact", "pi", "e"
    };
    return names.count(name) != 0;
}

Value complexUnary(const Value& value, const std::string& name,
                   double (*realFn)(double), Complex (*complexFn)(const Complex&)) {
    if (value.isComplex()) return Value(complexFn(value.getComplex()));
    if (value.isArray() || value.isString()) typeError(name, value);
    return Value(realFn(value.getNum()));
}

} // namespace

Value add(const Value& a, const Value& b) {
    if (a.isComplex() || b.isComplex()) return Value(asComplex(a, "+") + asComplex(b, "+"));
    return Value(asReal(a, "+") + asReal(b, "+"));
}

Value subtract(const Value& a, const Value& b) {
    if (a.isComplex() || b.isComplex()) return Value(asComplex(a, "-") - asComplex(b, "-"));
    return Value(asReal(a, "-") - asReal(b, "-"));
}

Value multiply(const Value& a, const Value& b) {
    if (a.isComplex() || b.isComplex()) return Value(asComplex(a, "*") * asComplex(b, "*"));
    return Value(asReal(a, "*") * asReal(b, "*"));
}

Value divide(const Value& a, const Value& b) {
    if (a.isComplex() || b.isComplex()) return Value(asComplex(a, "/") / asComplex(b, "/"));
    return Value(asReal(a, "/") / asReal(b, "/"));
}

Value remainder(const Value& a, const Value& b) {
    return Value(std::fmod(asReal(a, "%"), asReal(b, "%")));
}

Value power(const Value& a, const Value& b) {
    if (a.isComplex() || b.isComplex())
        return Value(std::pow(asComplex(a, "^"), asComplex(b, "^")));
    const double base = asReal(a, "^");
    const double exponent = asReal(b, "^");
    // A negative base with a fractional exponent has a principal complex
    // value; promote instead of returning NaN.
    if (base < 0.0 && exponent != std::floor(exponent))
        return Value(std::pow(Complex(base, 0.0), Complex(exponent, 0.0)));
    return Value(std::pow(base, exponent));
}

Value less(const Value& a, const Value& b) {
    if (a.isComplex() || b.isComplex())
        throw std::runtime_error("Cannot order complex numbers");
    return Value(asReal(a, "<") < asReal(b, "<") ? 1.0 : 0.0);
}

Value greater(const Value& a, const Value& b) {
    if (a.isComplex() || b.isComplex())
        throw std::runtime_error("Cannot order complex numbers");
    return Value(asReal(a, ">") > asReal(b, ">") ? 1.0 : 0.0);
}

bool truthy(const Value& value) {
    if (value.isComplex()) return value.getComplex() != Complex(0.0, 0.0);
    if (value.isArray()) return value.getArr() != nullptr;
    if (value.isString()) return !value.str.empty();
    return value.getNum() != 0.0;
}

std::string formatComplex(const Complex& value) {
    std::ostringstream out;
    out << value.real();
    const double imaginary = value.imag();
    out << (imaginary < 0.0 ? '-' : '+') << std::fabs(imaginary) << 'i';
    return out.str();
}

bool owns(const std::string& name) { return isOwnedName(name); }

bool execute(const std::string& name, std::vector<Value>& stack, std::size_t argc) {
    if (!isOwnedName(name)) return false;

    if (name == "complex" || name == "cplx") {
        requireArgs(name, argc, 2);
        const double imaginary = popReal(stack, name);
        const double real = popReal(stack, name);
        stack.push_back(Value(Complex(real, imaginary)));
        return true;
    }
    if (name == "re" || name == "real") {
        requireArgs(name, argc, 1);
        stack.push_back(Value(popComplex(stack, name).real()));
        return true;
    }
    if (name == "im" || name == "imag") {
        requireArgs(name, argc, 1);
        stack.push_back(Value(popComplex(stack, name).imag()));
        return true;
    }
    if (name == "abs" || name == "cabs") {
        requireArgs(name, argc, 1);
        const Value value = popValue(stack);
        if (value.isComplex()) stack.push_back(Value(std::abs(value.getComplex())));
        else stack.push_back(Value(std::fabs(asReal(value, name))));
        return true;
    }
    if (name == "conj") {
        requireArgs(name, argc, 1);
        stack.push_back(Value(std::conj(popComplex(stack, name))));
        return true;
    }
    if (name == "arg") {
        requireArgs(name, argc, 1);
        stack.push_back(Value(std::arg(popComplex(stack, name))));
        return true;
    }
    if (name == "cadd" || name == "csub" || name == "cmul" || name == "cdiv") {
        requireArgs(name, argc, 2);
        const Value b = popValue(stack);
        const Value a = popValue(stack);
        if (name == "cadd") stack.push_back(add(a, b));
        else if (name == "csub") stack.push_back(subtract(a, b));
        else if (name == "cmul") stack.push_back(multiply(a, b));
        else stack.push_back(divide(a, b));
        return true;
    }

    if (name == "pi") {
        requireArgs(name, argc, 0);
        stack.push_back(Value(3.141592653589793238462643383279502884));
        return true;
    }
    if (name == "e") {
        requireArgs(name, argc, 0);
        stack.push_back(Value(2.718281828459045235360287471352662498));
        return true;
    }

    if (name == "sin" || name == "cos" || name == "tan" ||
        name == "asin" || name == "acos" || name == "atan") {
        requireArgs(name, argc, 1);
        const Value value = popValue(stack);
        if (name == "sin") stack.push_back(complexUnary(value, name,
            [](double x) { return std::sin(x); },
            [](const Complex& z) { return std::sin(z); }));
        else if (name == "cos") stack.push_back(complexUnary(value, name,
            [](double x) { return std::cos(x); },
            [](const Complex& z) { return std::cos(z); }));
        else if (name == "tan") stack.push_back(complexUnary(value, name,
            [](double x) { return std::tan(x); },
            [](const Complex& z) { return std::tan(z); }));
        else if (name == "asin") stack.push_back(complexUnary(value, name,
            [](double x) { return std::asin(x); },
            [](const Complex& z) { return std::asin(z); }));
        else if (name == "acos") stack.push_back(complexUnary(value, name,
            [](double x) { return std::acos(x); },
            [](const Complex& z) { return std::acos(z); }));
        else stack.push_back(complexUnary(value, name,
            [](double x) { return std::atan(x); },
            [](const Complex& z) { return std::atan(z); }));
        return true;
    }

    if (name == "atan2" || name == "hypot" || name == "min" || name == "max") {
        requireArgs(name, argc, 2);
        const double b = popReal(stack, name);
        const double a = popReal(stack, name);
        if (name == "atan2") stack.push_back(Value(std::atan2(a, b)));
        else if (name == "hypot") stack.push_back(Value(std::hypot(a, b)));
        else if (name == "min") stack.push_back(Value(std::fmin(a, b)));
        else stack.push_back(Value(std::fmax(a, b)));
        return true;
    }

    if (name == "clamp") {
        requireArgs(name, argc, 3);
        const double high = popReal(stack, name);
        const double low = popReal(stack, name);
        const double value = popReal(stack, name);
        stack.push_back(Value(std::fmin(std::fmax(value, low), high)));
        return true;
    }
    if (name == "lerp") {
        requireArgs(name, argc, 3);
        const double t = popReal(stack, name);
        const double b = popReal(stack, name);
        const double a = popReal(stack, name);
        stack.push_back(Value(a + (b - a) * t));
        return true;
    }
    if (name == "deg" || name == "rad") {
        requireArgs(name, argc, 1);
        const double value = popReal(stack, name);
        constexpr double pi = 3.141592653589793238462643383279502884;
        stack.push_back(Value(name == "deg" ? value * 180.0 / pi : value * pi / 180.0));
        return true;
    }

    if (name == "sqrt") {
        requireArgs(name, argc, 1);
        const Value value = popValue(stack);
        if (value.isComplex()) {
            stack.push_back(Value(std::sqrt(value.getComplex())));
        } else {
            const double x = asReal(value, name);
            // Promote a negative real to the principal complex root so
            // sqrt(-1) is i rather than NaN.
            stack.push_back(x < 0.0 ? Value(Complex(0.0, std::sqrt(-x))) : Value(std::sqrt(x)));
        }
        return true;
    }
    if (name == "cbrt" || name == "exp" || name == "log" || name == "log10" ||
        name == "floor" || name == "ceil" || name == "round") {
        requireArgs(name, argc, 1);
        const Value value = popValue(stack);
        if (name == "cbrt") {
            stack.push_back(complexUnary(value, name,
                [](double x) { return std::cbrt(x); },
                [](const Complex& z) { return std::pow(z, 1.0 / 3.0); }));
        } else if (name == "exp") {
            stack.push_back(complexUnary(value, name,
                [](double x) { return std::exp(x); },
                [](const Complex& z) { return std::exp(z); }));
        } else if (name == "log") {
            if (value.isArray() || value.isString()) typeError(name, value);
            if (value.isComplex() || value.getNum() > 0.0) {
                stack.push_back(complexUnary(value, name,
                    [](double x) { return std::log(x); },
                    [](const Complex& z) { return std::log(z); }));
            } else if (value.getNum() == 0.0) {
                stack.push_back(Value(-std::numeric_limits<double>::infinity()));
            } else {
                stack.push_back(Value(Complex(std::log(-value.getNum()), 3.14159265358979323846)));
            }
        } else if (name == "log10") {
            if (value.isArray() || value.isString()) typeError(name, value);
            if (value.isComplex() || value.getNum() > 0.0) {
                stack.push_back(complexUnary(value, name,
                    [](double x) { return std::log10(x); },
                    [](const Complex& z) { return std::log10(z); }));
            } else if (value.getNum() == 0.0) {
                stack.push_back(Value(-std::numeric_limits<double>::infinity()));
            } else {
                constexpr double pi = 3.141592653589793238462643383279502884;
                stack.push_back(Value(Complex(std::log10(-value.getNum()), pi / std::log(10.0))));
            }
        } else if (name == "floor") {
            stack.push_back(Value(std::floor(asReal(value, name))));
        } else if (name == "ceil") {
            stack.push_back(Value(std::ceil(asReal(value, name))));
        } else {
            stack.push_back(Value(std::round(asReal(value, name))));
        }
        return true;
    }

    if (name == "sign") {
        requireArgs(name, argc, 1);
        const double value = popReal(stack, name);
        stack.push_back(Value((value > 0.0) - (value < 0.0)));
        return true;
    }

    if (name == "pow") {
        requireArgs(name, argc, 2);
        const Value exponent = popValue(stack);
        const Value base = popValue(stack);
        stack.push_back(power(base, exponent));
        return true;
    }

    if (name == "fact") {
        requireArgs(name, argc, 1);
        const double value = popReal(stack, name);
        if (value < 0.0 || value != std::floor(value))
            throw std::runtime_error("Factorial expects a non-negative integer");
        double result = 1.0;
        for (int i = 2; i <= static_cast<int>(value); ++i) result *= i;
        stack.push_back(Value(result));
        return true;
    }
    if (name == "multifact") {
        requireArgs(name, argc, 2);
        const double step = popReal(stack, name);
        const double value = popReal(stack, name);
        if (value < 0.0 || value != std::floor(value) || step < 1.0)
            throw std::runtime_error("Invalid arguments for multifact");
        double result = 1.0;
        for (double i = value; i > 0.0; i -= step) result *= i;
        stack.push_back(Value(result));
        return true;
    }

    return false;
}

} // namespace plusminus::math
