#pragma once
#include <string>
#include <vector>

enum class OpCode {
    PushConst, PushVar, Store,
    MakeArray, MakeArraySized, LoadIndex, StoreIndex,
    Add, Sub, Mul, Div, Mod, Pow,
    Less, Greater, And,
    Call,
    FuncDef, ProcDef, Return,
    GoCall, Sync,
    Lock, Unlock,
    Jmp, Jz, Pop, Halt
};

struct Command {
    OpCode op;
    double num = 0.0;
    std::string name;
    std::string str;
    bool isStr = false;
    int argc = 0;
    int target = -1;
    std::vector<std::string> params;
};
