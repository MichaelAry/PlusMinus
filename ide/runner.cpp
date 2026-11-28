#include "Parser.h"
#include "plusminus/math.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <limits>
#include <mutex>
#include <sstream>
#include <string>
#include <vector>

// JSON strings keep source output, diagnostics and inspection data separate.
static std::string quote(const std::string& s) {
    std::ostringstream out; out << '"';
    for (unsigned char ch : s) {
        switch (ch) {
            case '"': out << "\\\""; break;
            case '\\': out << "\\\\"; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default: if (ch < 32) out << "\\u00" << std::hex << std::setw(2) << std::setfill('0') << int(ch) << std::dec; else out << ch;
        }
    }
    out << '"'; return out.str();
}
static std::string number(double x) {
    std::ostringstream s; s << std::setprecision(std::numeric_limits<double>::max_digits10) << x; return s.str();
}
static const char* opcode(OpCode op) {
    switch (op) {
#define OP(x) case OpCode::x: return #x;
        OP(PushConst) OP(PushVar) OP(Store) OP(MakeArray) OP(MakeArraySized)
        OP(LoadIndex) OP(StoreIndex) OP(Add) OP(Sub) OP(Mul) OP(Div) OP(Mod) OP(Pow)
        OP(Less) OP(Greater) OP(And) OP(Call) OP(FuncDef) OP(ProcDef) OP(Return)
        OP(GoCall) OP(Sync) OP(Lock) OP(Unlock) OP(Jmp) OP(Jz) OP(Pop) OP(Halt)
#undef OP
    }
    return "Unknown";
}
static std::string listing(const std::vector<Command>& program) {
    std::ostringstream s;
    for (size_t i=0; i<program.size(); ++i) {
        const auto& c = program[i];
        s << std::setw(4) << i << "  " << opcode(c.op);
        if (!c.name.empty()) s << "  " << c.name;
        if (c.op == OpCode::PushConst) s << "  " << (c.isStr ? quote(c.str) : number(c.num));
        if (c.op == OpCode::Call || c.op == OpCode::GoCall || c.op == OpCode::MakeArray) s << "  argc=" << c.argc;
        if (c.target >= 0) s << "  -> " << c.target;
        for (const auto& p : c.params) s << "  " << p;
        s << '\n';
    }
    return s.str();
}
static std::string variables(const VM& vm) {
    std::vector<std::string> names;
    for (const auto& entry: vm.vars) names.push_back(entry.first);
    std::sort(names.begin(), names.end());
    std::ostringstream s;
    for (const auto& name: names) {
        const auto& v = vm.vars.at(name);
        s << name << " = ";
        if (v.isArray()) {
            s << '['; const auto& a = *v.getArr();
            for(size_t i=0; i<std::min<size_t>(a.size(), 200); ++i) { if(i) s << ", "; s << number(a[i]); }
            if(a.size()>200) s << ", ... (" << a.size() << " entries)";
            s << ']';
        } else if (v.isComplex()) s << plusminus::math::formatComplex(v.getComplex());
        else if (v.isString()) s << quote(v.str);
        else s << number(v.getNum());
        s << '\n';
    }
    return s.str();
}

static const char* plotKind(plusminus::PlotKind kind) {
    switch (kind) {
        case plusminus::PlotKind::Point: return "point";
        case plusminus::PlotKind::Dot: return "dot";
        case plusminus::PlotKind::Line: return "line";
    }
    return "point";
}

// JSON cannot represent NaN/Inf. A plotting program that produces a
// non-finite coordinate gets a finite 0 instead of an invalid document; the
// renderer can still show the remaining curves.
static std::string plotNumber(double value) {
    return std::isfinite(value) ? number(value) : std::string("0");
}

static std::string plotData(const std::vector<plusminus::PlotEvent>& events,
                            bool truncated, std::uint64_t threads) {
    std::ostringstream s;
    s << "{\"events\":[";
    bool first = true;
    for (const auto& event : events) {
        if (!first) s << ',';
        first = false;
        s << "{\"thread\":" << event.thread
          << ",\"kind\":\"" << plotKind(event.kind) << "\""
          << ",\"x\":" << plotNumber(event.x)
          << ",\"y\":" << plotNumber(event.y);
        if (event.kind == plusminus::PlotKind::Line)
            s << ",\"x2\":" << plotNumber(event.x2)
              << ",\"y2\":" << plotNumber(event.y2);
        s << '}';
    }
    s << "],\"truncated\":" << (truncated ? "true" : "false")
      << ",\"threads\":" << threads << "}";
    return s.str();
}
int main(int argc, char** argv) {
    const std::string mode = argc == 2 ? argv[1] : "run";
    if (mode != "run" && mode != "compile" && mode != "profile" && mode != "trace") { std::cerr << "Usage: plusminus_runner [run|compile|profile|trace]\n"; return 2; }
    std::string source{std::istreambuf_iterator<char>(std::cin), {}};
    std::string code, output, vars, result, error;
    std::string phase = "compile";
    using Clock = std::chrono::steady_clock;
    double compileMs = 0.0, executeMs = 0.0;
    size_t instructionCount = 0;
    size_t errorLine = 0, errorColumn = 0;
    std::string dynamicCounts = "{}";
    std::string capturedTrace = "[]";
    bool truncatedTrace = false;
    std::uint64_t executedInstructions = 0;
    std::vector<plusminus::PlotEvent> capturedPlots;
    bool truncatedPlots = false;
    std::uint64_t plotThreads = 0;
    try {
        auto compilationStart = Clock::now();
        auto program = compileToCommands(source);
        compileMs = std::chrono::duration<double, std::milli>(Clock::now() - compilationStart).count();
        instructionCount = program.size();
        code = listing(program);
        if (mode == "run" || mode == "profile" || mode == "trace") {
            phase = "runtime";
            VM vm;
            vm.profileEnabled = (mode == "profile" || mode == "trace");
            vm.traceEnabled = (mode == "trace");
            auto executionStart = Clock::now();
            try { result = number(vm.run(program)); }
            catch (...) {
                executeMs = std::chrono::duration<double, std::milli>(Clock::now() - executionStart).count();
                output = vm.output;
                {
                    std::lock_guard<std::mutex> lock(vm.plotMutex);
                    capturedPlots = vm.plotEvents;
                }
                truncatedPlots = vm.plotDropped.load(std::memory_order_relaxed) > 0;
                plotThreads = vm.plotThreadNext.load(std::memory_order_relaxed);
                throw;
            }
            executeMs = std::chrono::duration<double, std::milli>(Clock::now() - executionStart).count();
            output = vm.output;
            vars = variables(vm);
            {
                std::lock_guard<std::mutex> lock(vm.plotMutex);
                capturedPlots = vm.plotEvents;
            }
            truncatedPlots = vm.plotDropped.load(std::memory_order_relaxed) > 0;
            plotThreads = vm.plotThreadNext.load(std::memory_order_relaxed);
            if (vm.profileEnabled) {
                std::ostringstream counts;
                counts << "{";
                bool first = true;
                for (std::size_t index = 0; index < VM::OpcodeCount; ++index) {
                    const auto hits = vm.opcodeCounts[index].load(std::memory_order_relaxed);
                    if (hits == 0) continue;
                    executedInstructions += hits;
                    if (!first) counts << ",";
                    first = false;
                    counts << quote(opcode(static_cast<OpCode>(index))) << ":" << hits;
                }
                counts << "}";
                dynamicCounts = counts.str();
            }
            if (vm.traceEnabled) {
                std::ostringstream trace;
                trace << "[";
                bool first = true;
                for (const auto& event : vm.traceEvents) {
                    if (!first) trace << ",";
                    first = false;
                    trace << "{\"ip\":" << event.ip
                          << ",\"opcode\":" << quote(opcode(static_cast<OpCode>(event.opcode)))
                          << ",\"thread\":" << event.thread
                          << ",\"stack_depth\":" << event.stackDepth << "}";
                }
                trace << "]";
                capturedTrace = trace.str();
                truncatedTrace = vm.traceSeen.load(std::memory_order_relaxed) > vm.TraceLimit;
            }
        }
    } catch (const CompileError& e) {
        error = phase + ": " + e.what();
        errorLine = e.line;
        errorColumn = e.column;
    } catch (const std::exception& e) { error = phase + ": " + e.what(); }
      catch (...) { error = phase + ": unknown failure"; }
    std::ostringstream diagnostic;
    diagnostic << "[";
    if (!error.empty()) {
        diagnostic << "{\"severity\":\"error\",\"phase\":" << quote(phase)
                   << ",\"message\":" << quote(error)
                   << ",\"line\":" << errorLine
                   << ",\"column\":" << errorColumn << "}";
    }
    diagnostic << "]";
    std::cout << "{\"ok\":" << (error.empty() ? "true" : "false")
        << ",\"output\":" << quote(output) << ",\"result\":" << quote(result)
        << ",\"variables\":" << quote(vars) << ",\"bytecode\":" << quote(code)
        << ",\"plot\":" << plotData(capturedPlots, truncatedPlots, plotThreads)
        << ",\"error\":" << quote(error)
        << ",\"diagnostics\":" << diagnostic.str()
        << ",\"trace\":" << capturedTrace
        << ",\"trace_truncated\":" << (truncatedTrace ? "true" : "false")
        << ",\"metrics\":{\"compile_ms\":" << compileMs
        << ",\"execute_ms\":" << executeMs
        << ",\"program_instructions\":" << instructionCount
        << ",\"executed_instructions\":" << executedInstructions
        << ",\"opcode_hits\":" << dynamicCounts << "}}\n";
    return error.empty() ? 0 : 1;
}
