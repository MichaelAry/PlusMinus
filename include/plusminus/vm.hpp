#pragma once
#include "plusminus/value.hpp"
#include "plusminus/bytecode.hpp"
#include <cstddef>
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

    double run(const std::vector<Command>& program);

private:
    double executeThread(const std::vector<Command>& program, size_t startIp,
        std::vector<Frame> initialFrames, bool stopOnEmptyReturn);
    void syncAllThreads();
};
