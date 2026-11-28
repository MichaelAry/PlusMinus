import { readFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import { decodePlot, defaultViewport, encodePlot, pointRows, toData, toScreen, zoom,
  type Point, type PlotDocument } from "./document";
import { evaluate, parseExpression } from "./expression";
import { calculate, fit, sample, type PreviewRequest } from "./sampling";
import { PlotPreview } from "./preview";
import type { PreviewAnswer, PreviewMessage } from "./preview.worker";

function example(name: string): PlotDocument {
  const url = new URL(`../../../../../docs/plot-examples/${name}.pmplot`, import.meta.url);
  return decodePlot(readFileSync(url, "utf8"));
}

function finish<T>(job: Generator<undefined, T>): T {
  while (true) {
    const block = job.next();
    if (block.done) return block.value;
  }
}

describe("Studio 4 plot contract", () => {
  it.each(["waves-and-measurements", "powers-and-poles", "scatter-and-fit"])("round trips %s", name => {
    const document = example(name);
    expect(decodePlot(encodePlot(document))).toEqual(document);
  });

  it("rejects invalid values and duplicate identifiers with a field name", () => {
    const document = example("waves-and-measurements");
    const invalid = structuredClone(document);
    invalid.series[1].id = invalid.series[0].id;
    expect(() => encodePlot(invalid)).toThrow("series 2.id");
    invalid.series[1].id = document.series[1].id;
    invalid.viewport.xmax = -1;
    expect(() => encodePlot(invalid)).toThrow("viewport range");
    expect(pointRows([["0", "1e-3"], ["", "2"], ["0x01", "3"], ["0", "4"]]))
      .toEqual([[0, .001], [0, 4]]);
  });

  it("keeps the cursor anchor and fits visible data only", () => {
    const rect = { left: 55, top: 14, width: 1000, height: 600 };
    const position: Point = [564, 200];
    const anchor = toData(defaultViewport, rect, position);
    const pixels = toScreen(zoom(defaultViewport, anchor, .8), rect, anchor);
    expect(pixels[0]).toBeCloseTo(position[0]);
    expect(pixels[1]).toBeCloseTo(position[1]);
    const scatter = example("scatter-and-fit");
    expect(fit(scatter).xmax).toBe(5);
    scatter.series.forEach(series => { series.visible = series.id === "calibration"; });
    expect(fit(scatter)).toEqual({ xmin: 0, xmax: 2, ymin: .5, ymax: 2.5 });
    expect(fit({ ...scatter, series: [] })).toEqual(defaultViewport);
  });
});

describe("plot expressions and previews", () => {
  it.each([["-2^2", -4], ["(-2)^2", 4], ["2^3^2", 512], ["2^-2", .25],
    ["sin(0)", 0], ["pow(a,c)", 9]] as const)("evaluates %s", (text, value) => {
    expect(evaluate(parseExpression(text), 0, { a: 3, c: 2 })).toBe(value);
  });

  it("reports columns, bounds recursion and rejects undefined samples", () => {
    for (const text of ["sin(", "sin(1,2)", "2x", "unknown", "-".repeat(40) + "2", "2^".repeat(40) + "2"]) {
      expect(() => parseExpression(text)).toThrow(/column \d+/);
    }
    expect(evaluate(parseExpression("1/x"), 0, {})).toBeUndefined();
    expect(evaluate(parseExpression("(-1)^0.5"), 0, {})).toBeUndefined();
    const document = example("powers-and-poles");
    const formulas = document.series.filter(s => s.kind === "formula");
    const preview = finish(calculate({ revision: 7, formulas, width: 512, height: 300, view: document.viewport }));
    expect(preview.entries.find(r => r.id === "draft")?.error).toContain("column");
    expect(preview.entries.find(r => r.id === "parabola")?.segments?.length).toBeGreaterThan(0);
  });

  it("splits around sampled and unsampled poles but preserves a steep line", () => {
    for (const [text, pole, width] of [["1/x", 0, 257], ["1/(x-0.123)", .123, 256]] as const) {
      const segments = finish(sample(parseExpression(text), {}, defaultViewport, width, 300));
      expect(segments.length).toBeGreaterThan(1);
      expect(segments.some(segment => segment[0][0] < pole && segment.at(-1)![0] > pole)).toBe(false);
    }
    const line = finish(sample(parseExpression("1000*x"), {}, defaultViewport, 256, 300));
    expect(line).toHaveLength(1);
    expect(line[0]).toHaveLength(256);
  });

  it("allows only one running request and drops stale results", () => {
    class WorkerDouble {
      static instance: WorkerDouble;
      onmessage!: (event: { data: PreviewAnswer }) => void;
      messages: PreviewMessage[] = [];
      terminate = vi.fn();
      constructor() { WorkerDouble.instance = this; }
      postMessage(message: PreviewMessage) { this.messages.push(message); }
    }
    vi.useFakeTimers();
    vi.stubGlobal("Worker", WorkerDouble);
    const apply = vi.fn();
    const connection = new PlotPreview(apply, vi.fn());
    try {
      const request: Omit<PreviewRequest, "revision"> = { formulas: [], view: defaultViewport, width: 250, height: 80 };
      connection.schedule(request, 60);
      vi.advanceTimersByTime(60);
      connection.schedule({ ...request, width: 300 }, 16);
      connection.schedule({ ...request, width: 400 }, 16);
      vi.advanceTimersByTime(16);
      const worker = WorkerDouble.instance;
      expect(worker.messages.filter(message => "request" in message)).toHaveLength(1);
      worker.onmessage({ data: { revision: 1, preview: { revision: 1, entries: [] } } });
      expect(apply).not.toHaveBeenCalled();
      expect(worker.messages.at(-1)).toEqual({ request: { ...request, width: 400, revision: 3 } });
      worker.onmessage({ data: { revision: 3, preview: { revision: 3, entries: [] } } });
      expect(apply).toHaveBeenCalledOnce();
    } finally {
      connection.dispose();
      expect(WorkerDouble.instance.terminate).toHaveBeenCalledOnce();
      vi.unstubAllGlobals();
      vi.useRealTimers();
    }
  });
});
