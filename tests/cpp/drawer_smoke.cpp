#include "plusminus/api.hpp"
#include "plusminus/plot.hpp"
#include <cmath>
#include <iostream>
#include <set>
#include <string>
#include <vector>

namespace {

int failures = 0;

void expect(bool condition, const std::string& message) {
    if (condition) return;
    std::cerr << "FAIL: " << message << '\n';
    ++failures;
}

bool close(double a, double b) { return std::abs(a - b) < 1e-9; }

} // namespace

int main() {
    // --- Math library / complex numbers -------------------------------
    expect(close(evaluate("abs(complex(3, 4))"), 5.0), "abs(3+4i) = 5");
    expect(close(evaluate("re(complex(1.5, -2))"), 1.5), "re(1.5-2i)");
    expect(close(evaluate("im(complex(1.5, -2))"), -2.0), "im(1.5-2i)");
    expect(close(evaluate("re(complex(1, 2) * complex(3, 4))"), -5.0),
           "real part of (1+2i)(3+4i)");
    expect(close(evaluate("im(complex(1, 2) * complex(3, 4))"), 10.0),
           "imaginary part of (1+2i)(3+4i)");
    expect(close(evaluate("re(complex(1, 2) + complex(3, 4))"), 4.0), "complex addition");
    expect(close(evaluate("pow(complex(0, 1), 2)"), -1.0), "i^2 = -1");
    expect(close(evaluate("re(pow(-1, 0.5))"), 0.0), "fractional power of a negative real: real part");
    expect(close(evaluate("im(pow(-1, 0.5))"), 1.0), "fractional power of a negative real: imaginary part");
    expect(close(evaluate("sqrt(9)"), 3.0), "sqrt(9)");
    expect(close(evaluate("re(sqrt(-1))"), 0.0), "sqrt(-1) real part");
    expect(close(evaluate("im(sqrt(-1))"), 1.0), "sqrt(-1) imaginary part");
    expect(close(evaluate("re(log(-1))"), 0.0), "log(-1) real part");
    expect(close(evaluate("im(log(-1))"), 3.14159265358979323846), "log(-1) imaginary part");
    expect(close(evaluate("min(2, 3)"), 2.0), "min");
    expect(close(evaluate("max(2, 3)"), 3.0), "max");
    expect(close(evaluate("floor(2.9)"), 2.0), "floor");
    expect(close(evaluate("round(2.5)"), 3.0), "round");
    expect(close(evaluate("pi()"), 3.14159265358979323846), "pi()");
    expect(getOutput("print(complex(1, 2));") == "1+2i\n", "complex print formatting");

    auto vars = runAndGetVars("z = complex(1, 2); x = 5;");
    expect(vars.count("x") == 1 && close(vars["x"], 5.0), "real variable survives");
    expect(vars.count("z") == 0, "complex variable is not coerced to real");

    // --- Plot capture --------------------------------------------------
    auto primitives = getPlots("plot(1, 2); point(3, 4); line(0, 0, 5, 5);");
    expect(primitives.size() == 3, "three drawing primitives");
    if (primitives.size() == 3) {
        expect(primitives[0].kind == plusminus::PlotKind::Point, "plot is a curve point");
        expect(close(primitives[0].x, 1.0) && close(primitives[0].y, 2.0), "plot coordinates");
        expect(primitives[1].kind == plusminus::PlotKind::Dot, "point is a dot");
        expect(primitives[2].kind == plusminus::PlotKind::Line, "line is a segment");
        expect(close(primitives[2].x2, 5.0) && close(primitives[2].y2, 5.0), "line endpoint");
    }

    auto cleared = getPlots("plot(1, 1); clear(); plot(2, 2);");
    expect(cleared.size() == 1 && close(cleared[0].x, 2.0), "clear resets captured events");

    // --- Multithreaded drawing ----------------------------------------
    const std::string threaded = R"(
func mandel(cx, cy) {
    c = complex(cx, cy);
    z = complex(0, 0);
    i = 0;
    while (i < 20 && abs(z) < 2) {
        z = z * z + c;
        i = i + 1;
    }
    return i;
}
func row(y) {
    x = 0;
    while (x < 8) {
        plot(x, mandel(-2 + x, y));
        x = x + 1;
    }
}
r = 0;
while (r < 3) {
    go row(r);
    r = r + 1;
}
sync;
)";
    auto threadedPlots = getPlots(threaded);
    expect(threadedPlots.size() == 24, "three worker threads x eight points");
    std::set<std::uint64_t> workerThreads;
    for (const auto& event : threadedPlots) workerThreads.insert(event.thread);
    expect(workerThreads.size() == 3, "one colourable thread identifier per worker");
    expect(workerThreads.count(0) == 0, "main thread did not plot");

    if (failures == 0) std::cout << "PlusMinus drawer smoke: OK\n";
    return failures == 0 ? 0 : 1;
}
