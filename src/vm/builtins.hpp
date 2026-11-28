#pragma once
// Internal VM implementation detail: not part of PlusMinus's public API.
#include "plusminus/bytecode.hpp"
#include "plusminus/plot.hpp"
#include "plusminus/value.hpp"
#include <atomic>
#include <cstdint>
#include <mutex>
#include <string>
#include <vector>

// Shared state passed to built-ins from the executor. The plot buffer and its
// mutex let a worker thread emit drawing primitives without touching the VM's
// internal members directly.
struct BuiltinContext {
    std::string* output = nullptr;
    std::mutex* outputMutex = nullptr;
    std::vector<plusminus::PlotEvent>* plots = nullptr;
    std::mutex* plotsMutex = nullptr;
    std::atomic<std::uint64_t>* droppedPlots = nullptr;
    std::uint64_t threadId = 0;
};

// Execute a built-in language function and mutate the VM value stack.
// Returns false when the name is not a built-in and should be resolved by VM.
bool executeBuiltin(const Command& command, std::vector<Value>& stack,
                    BuiltinContext& context);
