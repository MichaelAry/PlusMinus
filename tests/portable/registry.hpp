#pragma once
#include <functional>
#include <string>
#include <utility>
#include <vector>
namespace pmtests {
struct Test { std::string id, group, source; std::function<void()> run; bool slow; };
inline std::vector<Test>& registry() { static std::vector<Test> all; return all; }
inline bool add(std::string id, std::string group, std::string source,
                std::function<void()> callback, bool slow) {
    registry().push_back({std::move(id),std::move(group),std::move(source),
                          std::move(callback),slow});
    return true;
}
}
