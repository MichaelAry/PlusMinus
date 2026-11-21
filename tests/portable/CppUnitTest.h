#pragma once
// Portable compatibility subset of the Microsoft test framework used by PlusMinus.
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
#include <type_traits>

#define TEST_CLASS(Name) struct Name
#define TEST_METHOD(Name) void Name()

namespace Microsoft { namespace VisualStudio { namespace CppUnitTestFramework {
struct TestFailure : std::runtime_error { using std::runtime_error::runtime_error; };
inline std::string narrow(const wchar_t* s) {
    if (!s) return "";
    std::string out;
    for (; *s; ++s) out.push_back(*s < 128 ? char(*s) : '?');
    return out;
}
struct Assert {
    template <class A, class B>
    static void AreEqual(const A& a, const B& b) {
        if constexpr (std::is_convertible_v<A, std::string> &&
                      std::is_convertible_v<B, std::string>) {
            if (std::string(a) != std::string(b)) throw TestFailure("String equality failed");
        } else if (!(a == b)) {
            throw TestFailure("Expected and actual values differ");
        }
    }
    template <class A, class B, class Extra>
    static void AreEqual(const A& a, const B& b, const Extra& extra) {
        if constexpr (std::is_arithmetic_v<Extra> &&
                      std::is_arithmetic_v<A> && std::is_arithmetic_v<B>) {
            if (!(std::abs(double(a) - double(b)) <= double(extra)))
                throw TestFailure("Numbers differ beyond tolerance");
        } else {
            AreEqual(a, b);
        }
    }
    template <class A, class B, class Delta, class Message>
    static void AreEqual(const A& a, const B& b, const Delta& d, const Message&) {
        AreEqual(a, b, d);
    }
    static void IsTrue(bool ok, const wchar_t* message=nullptr) {
        if (!ok) throw TestFailure(message ? narrow(message) : "Expected true");
    }
    static void IsFalse(bool ok, const wchar_t* message=nullptr) {
        if (ok) throw TestFailure(message ? narrow(message) : "Expected false");
    }
    static void Fail(const wchar_t* message=nullptr) {
        throw TestFailure(message ? narrow(message) : "Assertion failed");
    }
};
struct Logger {
    static void WriteMessage(const wchar_t* p) { if (p) std::wcerr << p; }
    static void WriteMessage(const char* p) { if (p) std::cerr << p; }
};
}}}
