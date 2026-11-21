#include "plusminus/vm.hpp"
#include <mutex>
#include <thread>
#include <utility>
#include <vector>

double VM::run(const std::vector<Command>& program) {
    vars.clear();
    output.clear();
    functions.clear();
    namedLocks.clear();
    threads.clear();

    // PRE-SCAN: регистрируем все функции ДО запуска потоков.
    // Это делает functions read-only во время выполнения -> безопасно без мьютекса.
    for (size_t i = 0; i < program.size(); ++i) {
        if (program[i].op == OpCode::FuncDef || program[i].op == OpCode::ProcDef) {
            FuncInfo fi;
            fi.params = program[i].params;
            fi.bodyStart = program[i].target;
            functions[program[i].name] = fi;
        }
    }

    try {
        // Главный поток: startIp=0, нет кадров, не выходим при Return
        return executeThread(program, 0, {}, false);
    }
    catch (...) {
        // Прибираем за собой потоки, чтобы не было std::terminate
        std::vector<std::thread> toJoin;
        {
            std::lock_guard<std::mutex> lock(threadsMutex);
            toJoin = std::move(threads);
        }
        for (auto& t : toJoin) if (t.joinable()) t.join();
        throw;
    }
}

void VM::syncAllThreads() {
    auto self = std::this_thread::get_id();
    while (true) {
        std::vector<std::thread> toJoin;
        {
            std::lock_guard<std::mutex> lock(threadsMutex);
            std::vector<std::thread> remaining;
            for (auto& t : threads) {
                if (t.get_id() == self) {
                    remaining.push_back(std::move(t)); // не join сами себя
                }
                else {
                    toJoin.push_back(std::move(t));
                }
            }
            threads = std::move(remaining);
        }
        if (toJoin.empty()) break;
        for (auto& t : toJoin) if (t.joinable()) t.join();
    }
}
