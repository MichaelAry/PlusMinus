#include "builtins.hpp"
#include "plusminus/math.hpp"
#include <cmath>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

double popReal(std::vector<Value>& stack, const char* name) {
    if (stack.empty()) throw std::runtime_error(std::string("Stack underflow in ") + name);
    Value value = stack.back();
    stack.pop_back();
    if (value.isArray()) throw std::runtime_error(std::string(name) + " expects numeric coordinates");
    if (value.isString()) throw std::runtime_error(std::string(name) + " expects numeric coordinates");
    if (value.isComplex()) throw std::runtime_error(std::string(name) + " expects real coordinates");
    return value.getNum();
}

void pushPlot(BuiltinContext& context, plusminus::PlotKind kind,
              double x, double y, double x2 = 0.0, double y2 = 0.0) {
    if (context.plots == nullptr || context.plotsMutex == nullptr) return;
    // The size check must happen under the same mutex as push_back: several
    // VM threads append concurrently.
    std::lock_guard<std::mutex> lock(*context.plotsMutex);
    if (context.plots->size() >= plusminus::PlotEventLimit) {
        if (context.droppedPlots) context.droppedPlots->fetch_add(1, std::memory_order_relaxed);
        return;
    }
    context.plots->push_back(plusminus::PlotEvent{kind, x, y, x2, y2, context.threadId});
}

} // namespace

bool executeBuiltin(const Command& c, std::vector<Value>& stack,
                    BuiltinContext& context) {
    // All non-trivial mathematics (including complex arithmetic) lives in the
    // Math library; this file only handles I/O, arrays and drawing.
    if (plusminus::math::execute(c.name, stack, static_cast<std::size_t>(c.argc))) return true;

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
            else if (arg.isComplex()) oss << plusminus::math::formatComplex(arg.getComplex());
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
            std::lock_guard<std::mutex> lock(*context.outputMutex);
            *context.output += oss.str() + "\n";
        }
        stack.push_back(Value(0.0));
        return true;
    }

    if (c.name == "resize") {
        if (c.argc != 2) throw std::runtime_error("resize expects 2 args");
        double newSize = popReal(stack, "resize");
        Value arrVal = stack.back(); stack.pop_back();
        if (!arrVal.isArray()) throw std::runtime_error("resize expects an array");
        arrVal.getArr()->resize((size_t)newSize, 0.0);
        stack.push_back(Value(0.0));
        return true;
    }

    if (c.name == "len") {
        if (c.argc != 1) throw std::runtime_error("len expects 1 arg");
        if (stack.empty()) throw std::runtime_error("Stack underflow in len");
        Value arg = stack.back(); stack.pop_back();
        if (!arg.isArray()) throw std::runtime_error("len expects an array");
        stack.push_back(Value(static_cast<double>(arg.getArr()->size())));
        return true;
    }

    // Drawing primitives. Arguments are real coordinates; the emitted event is
    // tagged with the calling VM thread so the UI can colour curves by thread.
    if (c.name == "plot") {
        if (c.argc != 2) throw std::runtime_error("plot expects 2 args: x, y");
        const double y = popReal(stack, "plot");
        const double x = popReal(stack, "plot");
        pushPlot(context, plusminus::PlotKind::Point, x, y);
        stack.push_back(Value(0.0));
        return true;
    }

    if (c.name == "point") {
        if (c.argc != 2) throw std::runtime_error("point expects 2 args: x, y");
        const double y = popReal(stack, "point");
        const double x = popReal(stack, "point");
        pushPlot(context, plusminus::PlotKind::Dot, x, y);
        stack.push_back(Value(0.0));
        return true;
    }

    if (c.name == "line") {
        if (c.argc != 4) throw std::runtime_error("line expects 4 args: x1, y1, x2, y2");
        const double y2 = popReal(stack, "line");
        const double x2 = popReal(stack, "line");
        const double y1 = popReal(stack, "line");
        const double x1 = popReal(stack, "line");
        pushPlot(context, plusminus::PlotKind::Line, x1, y1, x2, y2);
        stack.push_back(Value(0.0));
        return true;
    }

    if (c.name == "clear") {
        if (c.argc != 0) throw std::runtime_error("clear expects no arguments");
        if (context.plots != nullptr && context.plotsMutex != nullptr) {
            std::lock_guard<std::mutex> lock(*context.plotsMutex);
            context.plots->clear();
            if (context.droppedPlots) context.droppedPlots->store(0, std::memory_order_relaxed);
        }
        stack.push_back(Value(0.0));
        return true;
    }

    return false;
}
