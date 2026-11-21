#include "registry.hpp"
#include <algorithm>
#include <chrono>
#include <exception>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
static std::string quote(const std::string& value) {
    std::ostringstream stream;
    stream << '"';
    for (unsigned char ch : value) {
        switch (ch) {
        case '"': stream << "\\\""; break;
        case '\\': stream << "\\\\"; break;
        case '\n': stream << "\\n"; break;
        case '\r': stream << "\\r"; break;
        case '\t': stream << "\\t"; break;
        default:
            if (ch < 32) stream << "\\u00" << std::hex << std::setw(2)
                                << std::setfill('0') << int(ch) << std::dec;
            else stream << char(ch);
        }
    }
    stream << '"';
    return stream.str();
}
int main(int argc, char** argv) {
    std::string requested, suite="quick";
    bool list=false;
    for(int i=1; i<argc; ++i) {
        std::string arg=argv[i];
        if(arg=="--list") list=true;
        else if(arg=="--run" && i+1<argc) requested=argv[++i];
        else if(arg=="--suite" && i+1<argc) suite=argv[++i];
        else { std::cerr << "Unknown option: " << arg << '\n'; return 2; }
    }
    if(suite!="quick" && suite!="full") return 2;
    auto tests=pmtests::registry();
    std::sort(tests.begin(),tests.end(),[](const auto& a,const auto& b){return a.id<b.id;});
    if(list) {
        for(const auto& t:tests)
            std::cout << "{\"type\":\"test\",\"id\":" << quote(t.id)
                      << ",\"group\":" << quote(t.group)
                      << ",\"source\":" << quote(t.source)
                      << ",\"slow\":" << (t.slow?"true":"false") << "}\n";
        return 0;
    }
    int failed=0,selected=0;
    for(const auto& t:tests) {
        if(!requested.empty() && requested!=t.id) continue;
        if(requested.empty() && suite=="quick" && t.slow) continue;
        ++selected;
        auto start=std::chrono::steady_clock::now();
        std::string error;
        try { t.run(); }
        catch(const std::exception& exc) { error=exc.what(); }
        catch(...) { error="Unknown C++ exception"; }
        double ms=std::chrono::duration<double,std::milli>(
            std::chrono::steady_clock::now()-start).count();
        if(!error.empty()) ++failed;
        std::cout << "{\"type\":\"result\",\"id\":" << quote(t.id)
                  << ",\"group\":" << quote(t.group)
                  << ",\"status\":" << quote(error.empty()?"PASS":"FAIL")
                  << ",\"elapsed_ms\":" << std::setprecision(10) << ms
                  << ",\"error\":" << quote(error) << "}\n" << std::flush;
    }
    if(!requested.empty() && !selected) { std::cerr<<"Unknown test\n"; return 2; }
    return failed ? 1 : 0;
}
