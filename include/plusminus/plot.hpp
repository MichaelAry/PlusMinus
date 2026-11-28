#pragma once
#include <cstddef>
#include <cstdint>

namespace plusminus {

// Drawing primitives emitted by the interpreter's plotting built-ins.
// Each event carries the ordinal of the VM worker thread that produced it,
// so a renderer can assign one colour per thread and expose the concurrency
// of the drawing program itself.
enum class PlotKind : std::uint8_t {
    Point = 0, // point on the thread's polyline (connected curve)
    Dot = 1,   // unconnected point
    Line = 2,  // explicit segment
};

struct PlotEvent {
    PlotKind kind = PlotKind::Point;
    double x = 0.0;
    double y = 0.0;
    double x2 = 0.0;
    double y2 = 0.0;
    std::uint64_t thread = 0;
};

// Bounded capture keeps a runaway program from exhausting the runner's
// 8 MiB stdout/JSON budget (50k events stay comfortably below it). The runner
// reports truncation instead of silently dropping the fact that data was lost.
inline constexpr std::size_t PlotEventLimit = 50000;

} // namespace plusminus
