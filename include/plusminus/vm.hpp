#pragma once
#include "plusminus/value.hpp"
#include "plusminus/bytecode.hpp"
#include "plusminus/plot.hpp"
#include <cstddef>
#include <array>
#include <atomic>
#include <cstdint>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

class VM {
public:
    std::unordered_map<std::string, Value> vars;
    std::string output;

    struct FuncInfo {
        std::vector<std::string> params;
        size_t bodyStart;
    };
    struct Frame {
        std::unordered_map<std::string, Value> locals;
        size_t returnIp;
    };

    std::unordered_map<std::string, FuncInfo> functions;
    std::vector<std::thread> threads;
    std::unordered_map<std::string, std::unique_ptr<std::mutex>> namedLocks;

    // Мьютексы для защиты общего состояния
    std::mutex varsMutex;    // защищает vars
    std::mutex outputMutex;  // защищает output
    std::mutex threadsMutex; // защищает threads
    std::mutex locksMutex;   // защищает namedLocks map

    bool profileEnabled = false;
    static constexpr std::size_t OpcodeCount = static_cast<std::size_t>(OpCode::Halt) + 1;
    std::array<std::atomic<std::uint64_t>, OpcodeCount> opcodeCounts{};

    struct TraceEvent {
        std::size_t ip, stackDepth;
        std::uint32_t opcode;
        std::uint64_t thread;
    };
    bool traceEnabled = false;
    static constexpr std::size_t TraceLimit = 5000;
    std::atomic<std::uint64_t> traceSeen{0};
    std::atomic<std::uint64_t> traceThreadNext{0};
    std::mutex traceMutex;
    std::vector<TraceEvent> traceEvents;

    // Thread-tagged drawing primitives. Each executeThread() call receives a
    // stable ordinal, so the renderer can colour one curve per worker.
    std::mutex plotMutex;
    std::vector<plusminus::PlotEvent> plotEvents;
    std::atomic<std::uint64_t> plotThreadNext{0};
    std::atomic<std::uint64_t> plotDropped{0};

    double run(const std::vector<Command>& program);

private:
    double executeThread(const std::vector<Command>& program, size_t startIp,
        std::vector<Frame> initialFrames, bool stopOnEmptyReturn);
    void syncAllThreads();
};
