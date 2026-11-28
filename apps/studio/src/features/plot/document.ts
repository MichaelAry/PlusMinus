export const MAX_PLOT_BYTES = 2 * 1024 * 1024;
export const MAX_SERIES = 16;
export const MAX_POINTS = 10_000;
export const MAX_EXPRESSION = 512;
export const PARAMETERS = ["a", "b", "c"] as const;
export type Parameter = typeof PARAMETERS[number];
export type Parameters = Partial<Record<Parameter, number>>;
export type Point = [number, number];
export type Viewport = { xmin: number; xmax: number; ymin: number; ymax: number };

interface SeriesBase {
  id: string;
  label: string;
  color: string;
  visible: boolean;
}
export interface Formula extends SeriesBase {
  kind: "formula";
  expression: string;
  parameters: Parameters;
}
export interface Points extends SeriesBase {
  kind: "points";
  points: Point[];
}
export type Series = Formula | Points;
export interface PlotDocument {
  version: 1;
  viewport: Viewport;
  series: Series[];
}

export const defaultViewport: Viewport = { xmin: -10, xmax: 10, ymin: -2, ymax: 2 };
const axes = ["xmin", "xmax", "ymin", "ymax"] as const;

export function newSeries(kind: Series["kind"]): Series {
  const base = { id: crypto.randomUUID(), visible: true };
  return kind === "formula"
    ? { ...base, kind, label: "Formula", color: "#5AB0FF", expression: "sin(x)", parameters: {} }
    : { ...base, kind, label: "Points", color: "#F2AF57", points: [] };
}

export function newPlot(): PlotDocument {
  return { version: 1, viewport: { ...defaultViewport }, series: [newSeries("formula")] };
}

export function validViewport(view: Viewport): boolean {
  return axes.every(axis => Number.isFinite(view[axis])) &&
    view.xmin < view.xmax && view.ymin < view.ymax &&
    Number.isFinite(view.xmax - view.xmin) && Number.isFinite(view.ymax - view.ymin);
}

function invalid(field: string): never { throw new Error("Invalid " + field); }

function object(value: unknown, field: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) invalid(field);
  return value as Record<string, unknown>;
}

function finite(value: unknown, field: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) invalid(field);
  return value;
}

export function decodePlot(source: string): PlotDocument {
  if (new TextEncoder().encode(source).length > MAX_PLOT_BYTES) throw new Error("Plot file exceeds 2 MiB");
  const data = object(JSON.parse(source), "document");
  if (data.version !== 1) invalid("version");
  const bounds = object(data.viewport, "viewport");
  const viewport = {
    xmin: finite(bounds.xmin, "viewport.xmin"), xmax: finite(bounds.xmax, "viewport.xmax"),
    ymin: finite(bounds.ymin, "viewport.ymin"), ymax: finite(bounds.ymax, "viewport.ymax"),
  };
  if (!validViewport(viewport)) invalid("viewport range");
  if (!Array.isArray(data.series) || data.series.length > MAX_SERIES) invalid("series count");
  const ids = new Set<string>();
  let totalPoints = 0;
  const series = data.series.map((entry, index): Series => {
    const field = "series " + (index + 1);
    const { id, label, visible, color, kind, expression, parameters, points } = object(entry, field);
    if (typeof id !== "string" || !id || ids.has(id)) invalid(field + ".id");
    if (typeof label !== "string") invalid(field + ".label");
    if (typeof color !== "string" || !/^#[\da-f]{6}$/i.test(color)) invalid(field + ".color");
    if (typeof visible !== "boolean") invalid(field + ".visible");
    ids.add(id);
    const base = { id, label, visible, color };
    if (kind === "formula") {
      if (typeof expression !== "string" || [...expression].length > MAX_EXPRESSION) invalid(field + ".expression");
      const params: Parameters = {};
      for (const [name, value] of Object.entries(object(parameters, field + ".parameters"))) {
        const param = name as Parameter;
        const path = field + ".parameters." + name;
        if (!PARAMETERS.includes(param)) invalid(path);
        const n = finite(value, path);
        if (n < -10 || n > 10 || Math.abs(n * 100 - Math.round(n * 100)) > 1e-9) invalid(path);
        params[param] = n;
      }
      return { ...base, kind, expression, parameters: params };
    }
    if (kind !== "points") invalid(field + ".kind");
    if (!Array.isArray(points) || (totalPoints += points.length) > MAX_POINTS) invalid(field + ".points count");
    return { ...base, kind, points: points.map((row, index): Point => {
      const path = field + ".points row " + (index + 1);
      if (!Array.isArray(row) || row.length !== 2) invalid(path);
      return [finite(row[0], path + " X"), finite(row[1], path + " Y")];
    }) };
  });
  return { version: 1, viewport, series };
}

export function encodePlot(document: PlotDocument): string {
  const text = JSON.stringify(document, null, 2) + "\n";
  decodePlot(text);
  return text;
}

export type Rect = { left: number; top: number; width: number; height: number };

export function toScreen(view: Viewport, rect: Rect, [x, y]: Point): Point {
  return [rect.left + (x - view.xmin) / (view.xmax - view.xmin) * rect.width,
    rect.top + (view.ymax - y) / (view.ymax - view.ymin) * rect.height];
}

export function toData(view: Viewport, rect: Rect, [x, y]: Point): Point {
  return [view.xmin + (x - rect.left) / rect.width * (view.xmax - view.xmin),
    view.ymax - (y - rect.top) / rect.height * (view.ymax - view.ymin)];
}

export function zoom(view: Viewport, [x, y]: Point, factor: number): Viewport {
  return { xmin: x + (view.xmin - x) * factor, xmax: x + (view.xmax - x) * factor,
    ymin: y + (view.ymin - y) * factor, ymax: y + (view.ymax - y) * factor };
}

export function pan(view: Viewport, rect: Rect, dx: number, dy: number): Viewport {
  const x = -dx / rect.width * (view.xmax - view.xmin);
  const y = dy / rect.height * (view.ymax - view.ymin);
  return { xmin: view.xmin + x, xmax: view.xmax + x, ymin: view.ymin + y, ymax: view.ymax + y };
}

export function pointNumber(text: string): number | undefined {
  if (!/^[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:e[+-]?[0-9]+)?$/i.test(text.trim())) return;
  const n = Number(text);
  if (Number.isFinite(n)) return n;
}

export function pointRows(rows: readonly [string, string][]): Point[] {
  const points: Point[] = [];
  for (const [x, y] of rows) {
    const px = pointNumber(x), py = pointNumber(y);
    if (px !== undefined && py !== undefined) points.push([px, py]);
  }
  return points;
}
