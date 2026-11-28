import { defaultViewport, validViewport, type Formula, type Parameters, type PlotDocument,
  type Point, type Viewport } from "./document";
import { compile, evaluate, type Expression } from "./expression";

export type Segments = Point[][];
export interface PreviewRequest {
  revision: number;
  formulas: Formula[];
  view: Viewport;
  width: number;
  height: number;
}
export interface Preview {
  revision: number;
  entries: { id: string; segments?: Segments; error?: string }[];
}

type Sample = [number, number | undefined];

export function* sample(expr: Expression, params: Parameters, view: Viewport, width: number,
  height: number): Generator<undefined, Segments> {
  const count = Math.max(256, Math.min(2048, Math.round(width)));
  const yspan = view.ymax - view.ymin, xspan = view.xmax - view.xmin;
  let budget = 4 * count;
  const segments: Segments = [];
  let current: Point[] = [];
  const gap = () => {
    if (current.length) segments.push(current);
    current = [];
  };
  const add = ([x, y]: Sample) => {
    if (y === undefined) gap();
    else current.push([x,y]);
  };

  function inspect(left: Sample, right: Sample, depth: number): void {
    const [x0, y0] = left, [x1, y1] = right;
    if (y0 === undefined || y1 === undefined) {
      gap();
      add(right);
      return;
    }
    const mid = x0 + (x1 - x0) / 2;
    if (budget <= 0 || mid === x0 || mid === x1) {
      if (Math.abs(y1 / 2 - y0 / 2) / yspan > 1) gap();
      add(right);
      return;
    }
    budget--;
    const y = evaluate(expr, mid, params);
    if (y === undefined) {
      gap();
      add(right);
      return;
    }
    const delta = Math.abs(y - (y0 / 2 + y1 / 2)) / yspan * height;
    if (delta <= 2) add(right);
    else if (depth === 0) {
      if (delta > 12) gap();
      else add([mid, y]);
      add(right);
    } else {
      inspect(left, [mid, y], depth - 1);
      inspect([mid, y], right, depth - 1);
    }
  }

  let left: Sample = [view.xmin, evaluate(expr, view.xmin, params)];
  add(left);
  for (let i = 1; i < count; i++) {
    if (i % 256 === 0) yield;
    const x = i === count - 1 ? view.xmax : view.xmin + i / (count - 1) * xspan;
    const right: Sample = [x, evaluate(expr, x, params)];
    inspect(left, right, 4);
    left = right;
  }
  gap();
  return segments;
}

export function* calculate(request: PreviewRequest): Generator<undefined, Preview> {
  const entries: Preview["entries"] = [];
  for (const { id, expression, parameters } of request.formulas) {
    const parsed = compile(expression);
    if (parsed.error !== undefined) entries.push({ id, error: parsed.error });
    else {
      const segments = yield* sample(parsed.expression, parameters, request.view, request.width, request.height);
      entries.push({ id, segments });
    }
    yield;
  }
  return { revision: request.revision, entries };
}

export function fit(document: PlotDocument): Viewport {
  const formulas: Formula[] = [];
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  const extendY = (y: number) => { ymin = Math.min(ymin, y); ymax = Math.max(ymax, y); };
  for (const series of document.series) {
    if (!series.visible) continue;
    if (series.kind === "formula") formulas.push(series);
    else for (const [x,y] of series.points) {
      xmin = Math.min(xmin, x);
      xmax = Math.max(xmax, x);
      extendY(y);
    }
  }
  if (formulas.length) {
    xmin = Math.min(-10, xmin);
    xmax = Math.max(10, xmax);
    for (const formula of formulas) {
      const { expression } = compile(formula.expression);
      if (!expression) continue;
      for (let i = 0; i < 512; i++) {
        const fraction = i / 511;
        const x = xmin * (1 - fraction) + xmax * fraction;
        const y = evaluate(expression, x, formula.parameters);
        if (y !== undefined) extendY(y);
      }
    }
  }
  if (ymin === Infinity) return { ...defaultViewport };

  function limits(low: number, high: number, pad: boolean): [number, number] {
    const margin = low === high ? Math.max(1, Math.abs(low) * .05) : pad ? high / 20 - low / 20 : 0;
    return [Number.isFinite(low - margin) ? low - margin : low,
      Number.isFinite(high + margin) ? high + margin : high];
  }
  const [x0, x1] = limits(xmin, xmax, false), [y0, y1] = limits(ymin, ymax, true);
  const result = { xmin: x0, xmax: x1, ymin: y0, ymax: y1 };
  if (!validViewport(result)) throw new Error("Visible data exceeds the supported axis range");
  return result;
}
