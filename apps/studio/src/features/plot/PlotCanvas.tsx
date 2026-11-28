import { useLayoutEffect, useRef, useState, type PointerEvent } from "react";
import { pan, toData, toScreen, validViewport, zoom, type PlotDocument,
  type Point, type Rect, type Viewport } from "./document";
import type { Preview } from "./sampling";

interface Size { width: number; height: number; ratio: number }
interface Props {
  document: PlotDocument;
  preview: Preview | undefined;
  disabled: boolean;
  onResize: (rect: Rect) => void;
  onViewport: (view: Viewport) => void;
}

function dataRect({ width, height }: Size): Rect {
  return { left: 55, top: 14, width: Math.max(1, width - 73), height: Math.max(1, height - 44) };
}

function draw(canvas: HTMLCanvasElement, size: Size, document: PlotDocument, preview?: Preview) {
  const context = canvas.getContext("2d");
  if (!context) return;
  const { width, height, ratio } = size;
  const rect = dataRect(size);
  const { left, top } = rect, right = left + rect.width, bottom = top + rect.height;
  const view = document.viewport;
  const style = canvas.ownerDocument.defaultView!.getComputedStyle(canvas);
  const screen = (point: Point) => toScreen(view, rect, point);
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.fillStyle = style.backgroundColor;
  context.fillRect(0, 0, width, height);
  context.strokeStyle = style.borderColor;
  context.lineWidth = 1;
  context.strokeRect(left, top, rect.width, rect.height);
  context.fillStyle = style.color;
  context.font = "11px system-ui";
  const label = (n: number) => Number(n.toPrecision(4)).toString();
  for (let i = 0; i <= 4; ++i) {
    const fraction = i / 4;
    const x = label(view.xmin + fraction * (view.xmax - view.xmin));
    const y = label(view.ymin + fraction * (view.ymax - view.ymin));
    context.fillText(x, left + rect.width * fraction - context.measureText(x).width / 2, bottom + 18);
    context.fillText(y, 4, bottom - rect.height * fraction + 4, 47);
  }

  context.save();
  context.beginPath();
  context.rect(left, top, rect.width, rect.height);
  context.clip();
  const [zeroX, zeroY] = screen([0, 0]);
  context.beginPath();
  if (zeroX >= left && zeroX <= right) { context.moveTo(zeroX, top); context.lineTo(zeroX, bottom); }
  if (zeroY >= top && zeroY <= bottom) { context.moveTo(left, zeroY); context.lineTo(right, zeroY); }
  context.stroke();

  const entries = new Map(preview?.entries.map(entry => [entry.id, entry.segments]));
  for (const series of document.series) {
    if (!series.visible) continue;
    context.beginPath();
    if (series.kind === "points") {
      context.fillStyle = series.color;
      for (const point of series.points) {
        const [x, y] = screen(point);
        if (x >= left - 4 && x <= right + 4 && y >= top - 4 && y <= bottom + 4) {
          context.moveTo(x + 3, y);
          context.arc(x, y, 3, 0, Math.PI * 2);
        }
      }
      context.fill();
    } else {
      context.strokeStyle = series.color;
      context.lineWidth = 1.8;
      for (const segment of entries.get(series.id) ?? []) {
        let started = false;
        for (const point of segment) {
          const [x, y] = screen(point);
          if (!Number.isFinite(x) || !Number.isFinite(y)) { started = false; continue; }
          if (started) context.lineTo(x, y);
          else context.moveTo(x, y);
          started = true;
        }
      }
      context.stroke();
    }
  }
  context.restore();
}

function sameLayers(before: PlotDocument, after: PlotDocument) {
  return before.viewport === after.viewport && before.series.length === after.series.length &&
    before.series.every((series, index) => {
      const next = after.series[index];
      return series.id === next.id && series.visible === next.visible && series.color === next.color &&
        (series.kind === "formula" ? next.kind === "formula" :
          next.kind === "points" && series.points === next.points);
    });
}

export function PlotCanvas(props: Props) {
  const ref = useRef<HTMLCanvasElement>(null);
  const drag = useRef<{ id: number; point: Point } | undefined>(undefined);
  const [size, setSize] = useState<Size>({ width: 0, height: 0, ratio: 1 });
  const latest = useRef(props);
  const viewport = useRef(props.document.viewport);
  const painted = useRef<{ size: Size; document: PlotDocument; preview?: Preview } | undefined>(undefined);
  useLayoutEffect(() => {
    latest.current = props;
    viewport.current = props.document.viewport;
  }, [props]);

  function position(event: { clientX: number; clientY: number }): Point {
    const { left, top } = ref.current!.getBoundingClientRect();
    return [event.clientX - left, event.clientY - top];
  }
  function contains([x,y]: Point, rect: Rect) {
    return x >= rect.left && x <= rect.left + rect.width && y >= rect.top && y <= rect.top + rect.height;
  }
  function update(view: Viewport) {
    if (validViewport(view)) {
      viewport.current = view;
      latest.current.onViewport(view);
    }
  }

  useLayoutEffect(() => {
    const canvas = ref.current!;
    function resize() {
      const { width, height } = canvas.getBoundingClientRect();
      const ratio = Math.min(2, canvas.ownerDocument.defaultView?.devicePixelRatio || 1);
      setSize(before => before.width === width && before.height === height && before.ratio === ratio
        ? before : { width, height, ratio });
    }
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();
    return () => observer.disconnect();
  }, []);
  useLayoutEffect(() => {
    if (size.width && size.height) latest.current.onResize(dataRect(size));
  }, [size]);
  useLayoutEffect(() => {
    const canvas = ref.current!;
    function wheel(event: WheelEvent) {
      const { disabled } = latest.current;
      const rect = dataRect(size), point = position(event);
      if (disabled || !event.deltaY || !contains(point, rect)) return;
      event.preventDefault();
      canvas.focus({ preventScroll: true });
      const steps = event.deltaY / (event.deltaMode === 1 ? 3 : event.deltaMode === 2 ? 1 : 120);
      update(zoom(viewport.current, toData(viewport.current, rect, point),
        1.2 ** Math.max(-10, Math.min(10, steps))));
    }
    canvas.addEventListener("wheel", wheel, { passive: false });
    return () => canvas.removeEventListener("wheel", wheel);
  }, [size]);
  useLayoutEffect(() => {
    const previous = painted.current;
    if (!size.width || !size.height) return;
    if (previous?.size === size && previous.preview === props.preview &&
      sameLayers(previous.document, props.document)) return;
    draw(ref.current!, size, props.document, props.preview);
    painted.current = { size, document: props.document, preview: props.preview };
  }, [size, props.document, props.preview]);

  function pointerDown(event: PointerEvent<HTMLCanvasElement>) {
    const point = position(event);
    if (props.disabled || event.button !== 0 || !contains(point, dataRect(size))) return;
    event.currentTarget.focus({ preventScroll: true });
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { id: event.pointerId, point };
  }
  function pointerMove(event: PointerEvent<HTMLCanvasElement>) {
    if (props.disabled || drag.current?.id !== event.pointerId) return;
    const point = position(event);
    const [x, y] = drag.current.point;
    drag.current.point = point;
    update(pan(viewport.current, dataRect(size), point[0] - x, point[1] - y));
  }
  function stopDrag(event: PointerEvent<HTMLCanvasElement>) {
    if (drag.current?.id === event.pointerId) drag.current = undefined;
  }

  return <div className="plot-canvas-host"><canvas ref={ref} className="plot-canvas" tabIndex={0} aria-label="Plot canvas"
    width={Math.ceil(size.width * size.ratio)} height={Math.ceil(size.height * size.ratio)}
    data-preview-revision={props.preview?.revision}
    onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={stopDrag}
    onPointerCancel={stopDrag} onLostPointerCapture={stopDrag}/></div>;
}
