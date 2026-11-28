// Mandelbrot — default multithreaded drawing example.
//
// Each `go row(...)` worker computes one horizontal slice of the set and
// emits one connected curve. The Drawer receives every point tagged with the
// worker's thread id, so curves can be coloured per thread.
//
// Run through plusminus_runner and inspect either:
//   * report.plot.events — thread-tagged drawing primitives, or
//   * report.bytecode     — the compiled listing of this program.

func mandel(cx, cy) {
    c = complex(cx, cy);
    z = complex(0, 0);
    i = 0;
    while (i < 80 && abs(z) < 2) {
        z = z * z + c;
        i = i + 1;
    }
    return i;
}

func row(rowIndex) {
    x = 0;
    while (x < 160) {
        cx = -2.2 + x * 0.0175;
        cy = -1.2 + rowIndex * 0.075;
        plot(cx, mandel(cx, cy));
        x = x + 1;
    }
}

r = 0;
while (r < 32) {
    go row(r);
    r = r + 1;
}
sync;
print("Mandelbrot rows rendered by 32 worker threads");
