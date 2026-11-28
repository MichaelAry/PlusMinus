import { useLayoutEffect, useRef, useState } from "react";
import type { IDockviewPanelProps } from "dockview-react";
import { MAX_EXPRESSION, MAX_POINTS, MAX_SERIES, newSeries, pointNumber, pointRows,
  type Formula, type Parameter, type Points, type Rect, type Series, type Viewport } from "./document";
import { compile } from "./expression";
import { fit, type Preview } from "./sampling";
import { PlotCanvas } from "./PlotCanvas";
import { PlotPreview } from "./preview";
import { createPlot, editPlot, openPlot, plotMessage, savePlot, usePlot } from "./store";

const PAGE_SIZE = 100;

function updateSeries(id: string, update: (series: Series) => Series) {
  editPlot(({ document }) => ({
    document: { ...document, series: document.series.map(series => series.id === id ? update(series) : series) },
  }));
}

function changeViewport(viewport: Viewport) {
  editPlot(({ document }) => ({ document: { ...document, viewport } }));
}

function ParameterField({ name, value, onChange }: {
  name: Parameter; value: number; onChange: (value: number) => void;
}) {
  const [draft, setDraft] = useState<string>();
  const normalize = (raw: number) => Math.min(10, Math.max(-10, Math.round(raw * 100) / 100));
  return <div className="plot-parameter">
    <label htmlFor={`plot-slider-${name}`}>{name}</label>
    <input id={`plot-slider-${name}`} aria-label={`Parameter ${name} slider`} type="range"
      min={-10} max={10} step={.01} value={value} onChange={event => {
        setDraft(undefined);
        onChange(event.currentTarget.valueAsNumber);
      }}/>
    <input aria-label={`Parameter ${name} value`} type="number" min={-10} max={10} step={.01}
      value={draft ?? value} onChange={event => {
        const { value, valueAsNumber } = event.currentTarget;
        setDraft(value);
        if (Number.isFinite(valueAsNumber)) onChange(normalize(valueAsNumber));
      }}
      onBlur={() => setDraft(undefined)}
      onKeyDown={event => { if (event.key === "Enter") event.currentTarget.blur(); }}/>
  </div>;
}

function FormulaEditor({ series }: { series: Formula }) {
  const parsed = compile(series.expression);
  const diagnostic = parsed.error;
  return <div className="plot-formula">
    <label htmlFor="plot-expression">y =</label>
    <input id="plot-expression" aria-label="Formula" data-plot-editor-focus
      spellCheck={false} autoComplete="off" maxLength={MAX_EXPRESSION}
      title="Decimal numbers start with a digit. Use x, a, b, c, +, -, *, /, ^, sin, cos and pow. Angles are in radians. Parameters default to 1 and range from -10 to 10 in steps of 0.01."
      value={series.expression} aria-invalid={!!diagnostic}
      onChange={event => {
        const expression = event.currentTarget.value;
        updateSeries(series.id, current => ({ ...current as Formula, expression }));
      }}/>
    {diagnostic && <p className="plot-error" role="status">{diagnostic}</p>}
    {parsed.expression?.parameters.map(name => <ParameterField key={name} name={name}
      value={series.parameters[name] ?? 1} onChange={value => updateSeries(series.id, current => ({
        ...current as Formula, parameters: { ...(current as Formula).parameters, [name]: value },
      }))}/>)}
  </div>;
}

function PointTable({ series }: { series: Points }) {
  const draft = usePlot(state => state.drafts.get(series.id));
  const rows: [string, string][] = draft ?? series.points.map(([x, y]) => [String(x), String(y)]);
  const count = usePlot(state => state.document.series.reduce((total, series) =>
    total + (series.kind === "points" ? state.drafts.get(series.id)?.length ?? series.points.length : 0), 0));
  const [page, setPage] = useState(0);
  const [currentRow, selectRow] = useState(-1);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const pageStart = page * PAGE_SIZE;
  const focusRow = useRef<number | undefined>(undefined);
  const table = useRef<HTMLTableElement>(null);

  function change(next: [string, string][]) {
    const points = pointRows(next);
    editPlot(state => ({
      drafts: new Map(state.drafts).set(series.id, next),
      document: { ...state.document, series: state.document.series.map(item =>
        item.id === series.id ? { ...series, points } : item) },
    }));
  }

  useLayoutEffect(() => {
    if (focusRow.current !== undefined) {
      table.current?.querySelector<HTMLInputElement>(`[data-x-row="${focusRow.current}"]`)?.focus();
      focusRow.current = undefined;
    }
  });

  return <div className="plot-point-editor">
    <table className="plot-points" ref={table} aria-label="Points">
      <thead><tr><th scope="col">X</th><th scope="col">Y</th></tr></thead>
      <tbody>
        {rows.slice(pageStart, pageStart + PAGE_SIZE).map((row, index) => {
          const rowIndex = index + pageStart;
          return <tr key={rowIndex} className={rowIndex === currentRow ? "selected" : ""}>
            {row.map((text, column) => <td key={column}>
              <input value={text} inputMode="decimal" spellCheck={false}
                data-x-row={column === 0 ? rowIndex : undefined}
                data-plot-editor-focus={index === 0 && column === 0 ? true : undefined}
                aria-label={`${column === 0 ? "X" : "Y"} row ${rowIndex + 1}`}
                aria-invalid={pointNumber(text) === undefined}
                onFocus={() => selectRow(rowIndex)}
                onChange={event => {
                  const next = rows.slice();
                  next[rowIndex] = [...row];
                  next[rowIndex][column] = event.currentTarget.value;
                  change(next);
                }}/>
            </td>)}
          </tr>;
        })}
      </tbody>
    </table>
    <div className="plot-row-actions">
      <button type="button" data-plot-editor-focus={!rows.length || undefined} disabled={count >= MAX_POINTS}
        onClick={() => {
          focusRow.current = rows.length;
          setPage(Math.floor(rows.length / PAGE_SIZE));
          selectRow(rows.length);
          change([...rows, ["", ""]]);
        }}>Add row</button>
      <button type="button" disabled={currentRow < 0 || currentRow >= rows.length}
        onClick={() => {
          const next = rows.filter((_, index) => index !== currentRow);
          change(next);
          selectRow(-1);
          setPage(Math.min(page, Math.max(0, Math.ceil(next.length / PAGE_SIZE) - 1)));
        }}>Remove row</button>
    </div>
    {pages > 1 && <div className="plot-row-actions">
      <button type="button" disabled={page === 0} onClick={() => { setPage(page - 1); selectRow(-1); }}>Previous</button>
      <span>Page {page + 1} / {pages}</span>
      <button type="button" disabled={page + 1 >= pages} onClick={() => { setPage(page + 1); selectRow(-1); }}>Next</button>
    </div>}
  </div>;
}

function PlotWorkspace() {
  const document = usePlot(state => state.document);
  const selected = usePlot(state => state.selected);
  const busy = usePlot(state => state.busy);
  const series = document.series.find(item => item.id === selected);
  const split = useRef<HTMLDivElement>(null);
  const [sidebar, setSidebar] = useState(246);
  const [preview, setPreview] = useState<Preview>();
  const [rect, setRect] = useState<Rect>();
  const worker = useRef<PlotPreview | null>(null);
  const previousExpressions = useRef(new Map<string, string>());
  const formulas = document.series.filter((s): s is Formula => s.kind === "formula" && s.visible);
  const key = JSON.stringify(formulas.map(({ id, expression, parameters }) => [id, expression, parameters]));
  const { viewport } = document;

  useLayoutEffect(() => {
    let connection: PlotPreview;
    try { connection = new PlotPreview(setPreview, plotMessage); }
    catch (error) { plotMessage(String(error)); return; }
    worker.current = connection;
    return () => { worker.current = null; connection.dispose(); };
  }, []);
  useLayoutEffect(() => {
    if (!rect) return;
    const previous = previousExpressions.current;
    const textChanged = formulas.some(({ id, expression }) => previous.has(id) && previous.get(id) !== expression);
    previousExpressions.current = new Map(formulas.map(({ id, expression }) => [id, expression]));
    worker.current?.schedule({ formulas, view: viewport, width: rect.width, height: rect.height }, textChanged ? 60 : 16);
  }, [key, viewport, rect]);

  function add(kind: Series["kind"]) {
    const next = newSeries(kind);
    editPlot(({ document }) => ({ document: { ...document, series: [...document.series, next] }, selected: next.id }));
  }
  function remove() {
    if (!series) return;
    const index = document.series.indexOf(series);
    const items = document.series.filter(item => item !== series);
    editPlot(state => {
      const drafts = new Map(state.drafts);
      drafts.delete(series.id);
      return { document: { ...document, series: items }, selected: items[Math.min(index, items.length - 1)]?.id ?? null, drafts };
    });
  }

  return <div className="plot-split" ref={split}
    style={{ gridTemplateColumns: `clamp(156px, ${sidebar}px, 55%) 8px minmax(0, 1fr)` }}>
    <fieldset className="plot-series-editor" disabled={busy} aria-label="Plot series">
      <div className="plot-row-actions">
        <button type="button" data-plot-editor-focus={!series || undefined}
          disabled={document.series.length >= MAX_SERIES} onClick={() => add("formula")}>Add formula</button>
        <button type="button" disabled={document.series.length >= MAX_SERIES} onClick={() => add("points")}>Add points</button>
      </div>
      <ul className="plot-series">
        {document.series.map(item => <li key={item.id} className={item === series ? "selected" : ""}>
          <input type="checkbox" aria-label={`Show ${item.label}`} checked={item.visible}
            onChange={event => {
              const visible = event.currentTarget.checked;
              updateSeries(item.id, old => ({ ...old, visible }));
            }}/>
          <span title={item.color} className="plot-swatch" style={{ backgroundColor: item.color }} />
          <button type="button" aria-pressed={item === series} title={item.label}
            onClick={() => usePlot.setState({ selected: item.id })}>{item.label || "(Unnamed)"}</button>
        </li>)}
      </ul>
      {series && <>
        <div className="plot-series-fields">
          <label>Name <input value={series.label} onChange={event => {
            const label = event.currentTarget.value;
            updateSeries(series.id, old => ({ ...old, label }));
          }}/></label>
          <label>Color <input type="color" value={series.color.toLowerCase()} onChange={event => {
            const color = event.currentTarget.value;
            updateSeries(series.id, old => ({ ...old, color }));
          }}/></label>
          <button type="button" onClick={remove}>Remove</button>
        </div>
        {series.kind === "formula"
          ? <FormulaEditor key={series.id} series={series}/>
          : <PointTable key={series.id} series={series}/>}
      </>}
    </fieldset>
    <div className="plot-divider" role="separator" aria-orientation="vertical" aria-label="Series editor width" tabIndex={0}
      onPointerDown={event => { if (event.button === 0) event.currentTarget.setPointerCapture(event.pointerId); }}
      onPointerMove={event => {
        if (event.currentTarget.hasPointerCapture(event.pointerId)) {
          const bounds = split.current!.getBoundingClientRect();
          setSidebar(Math.max(156, Math.min(bounds.width * .55, event.clientX - bounds.left)));
        }
      }}
      onKeyDown={event => {
        if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
          event.preventDefault();
          const max = split.current!.getBoundingClientRect().width * .55;
          const delta = event.key === "ArrowRight" ? 12 : -12;
          setSidebar(value => Math.max(156, Math.min(max, value + delta)));
        }
      }}/>
    <PlotCanvas document={document} preview={preview} disabled={busy} onResize={setRect} onViewport={changeViewport}/>
  </div>;
}

export function PlotPanel({ api, containerApi }: IDockviewPanelProps) {
  const generation = usePlot(state => state.generation);
  const busy = usePlot(state => state.busy);
  const dirty = usePlot(state => state.dirty);
  const path = usePlot(state => state.file?.path);
  const message = usePlot(state => state.message);
  const [location, setLocation] = useState(api.location.type);
  const [moving, setMoving] = useState(false);
  const editor = useRef<HTMLElement>(null);

  useLayoutEffect(() => {
    function focus() {
      if (api.isActive) editor.current?.querySelector<HTMLElement>("[data-plot-editor-focus]")?.focus();
    }
    const active = api.onDidActiveChange(focus);
    const location = api.onDidLocationChange(() => setLocation(api.location.type));
    if (api.isActive) focus();
    return () => { active.dispose(); location.dispose(); };
  }, [api, generation]);

  async function toggleDock() {
    const panel = containerApi.getPanel(api.id);
    if (!panel || moving) return;
    if (api.location.type === "grid") {
      setMoving(true);
      try {
        if (!await containerApi.addPopoutGroup(panel, {
          position: { left: 140, top: 120, width: 1050, height: 640 },
          onDidOpen: ({ window }) => window.focus(),
        })) {
          containerApi.addFloatingGroup(panel, { width: 760, height: 520 });
          plotMessage("Opened as a floating panel because the host did not allow a separate window.");
        }
      } finally { setMoving(false); }
    } else {
      const editorPanel = containerApi.getPanel("source-editor");
      if (editorPanel) api.moveTo({ group: editorPanel.group, position: "right" });
      else if (api.location.type === "popout") api.getWindow().close();
    }
  }

  return <section className="plot-panel" ref={editor} aria-label="Plot Editor"
    onPointerDown={() => { if (!api.isActive) api.setActive(); }}
    onFocus={() => { if (!api.isActive) api.setActive(); }}>
    <div className="plot-toolbar">
      <button disabled={busy} onClick={event => void createPlot(event.currentTarget.ownerDocument)}>New</button>
      <button disabled={busy} onClick={event => void openPlot(event.currentTarget.ownerDocument)}>Open</button>
      <button disabled={busy} onClick={() => void savePlot()}>Save</button>
      <button disabled={busy} onClick={() => void savePlot(true)}>Save As</button>
      <button disabled={busy} onClick={() => {
        try { changeViewport(fit(usePlot.getState().document)); }
        catch (error) { plotMessage(String(error)); }
      }}>Fit</button>
      <button disabled={busy || moving} onClick={() => void toggleDock()}>
        {location === "grid" ? "Detach" : "Dock"}
      </button>
      <span className="plot-file" title={path}>{path?.split(/[\\/]/).at(-1) ?? "Untitled.pmplot"}{dirty ? " ●" : ""}</span>
    </div>
    <PlotWorkspace key={generation}/>
    {message && <div className="plot-message" role="status" title={message}>{message}</div>}
  </section>;
}
