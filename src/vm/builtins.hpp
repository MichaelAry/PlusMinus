#pragma once
// Internal VM implementation detail: not part of PlusMinus's public API.
#include "plusminus/bytecode.hpp"
#include "plusminus/value.hpp"
#include <mutex>
#include <string>
#include <vector>

// Execute a built-in language function and mutate the VM value stack.
// Returns false when the name is not a built-in and should be resolved by VM.
bool executeBuiltin(const Command& command, std::vector<Value>& stack,
                    std::string& output, std::mutex& outputMutex);
