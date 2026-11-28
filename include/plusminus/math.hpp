#pragma once
#include "plusminus/value.hpp"
#include <complex>
#include <cstddef>
#include <string>
#include <vector>

// PlusMinus Math library.
//
// All non-trivial arithmetic lives here instead of being scattered through
// the VM: complex-aware binary operators, the scalar mathematical built-ins
// (sin/cos/sqrt/...) and the complex-number helpers used by Mandelbrot-style
// programs. The interpreter and the runner both include this public header.
namespace plusminus::math {

using Complex = std::complex<double>;

// Binary operators used by the VM executor. Operands are promoted to complex
// automatically when either side is complex; arrays and strings are rejected.
Value add(const Value& a, const Value& b);
Value subtract(const Value& a, const Value& b);
Value multiply(const Value& a, const Value& b);
Value divide(const Value& a, const Value& b);
Value remainder(const Value& a, const Value& b);
Value power(const Value& a, const Value& b);
Value less(const Value& a, const Value& b);
Value greater(const Value& a, const Value& b);
bool truthy(const Value& value);

// True when `name` is a built-in provided by the Math library.
bool owns(const std::string& name);

// Execute a Math built-in. Returns false for names this library does not own.
// The stack uses the same argument order as the VM: the last argument is on
// top. Arity and type errors throw std::runtime_error.
bool execute(const std::string& name, std::vector<Value>& stack, std::size_t argc);

// Stable textual form used by print() and the runner's variable dump.
std::string formatComplex(const Complex& value);

} // namespace plusminus::math
