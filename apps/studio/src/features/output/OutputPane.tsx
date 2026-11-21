import { useState } from "react";
import { useStudio } from "../../model/studio";
import { formatMetric, renderOutput } from "./present";
import type { RunResponse } from "../../api/contracts";
import { TraceReplay } from "./TraceReplay";

type View = "output" | "diagnostics" | "metrics" | "bytecode" | "trace";

export function OutputPane() {
  const [view, setView] = useState<View>("output");
  // Primitive selectors: returning a freshly allocated object on every render
  // creates an unstable external-store snapshot in React 19.
  const response = useStudio((s) => s.response);
  const transportError = useStudio((s) => s.transportError);
  const runningJob = useStudio((s) => s.runningJob);
  return <OutputContents view={view} setView={setView}
    response={response} transportError={transportError} runningJob={runningJob} />;
}

function OutputContents({ view, setView, response, transportError, runningJob }: {
  view: View;
  setView: (view: View) => void;
  response: RunResponse | null;
  transportError: string | null;
  runningJob: string | null;
}) {
  const report = response?.report;
  return (
    <div className="output-pane">
      <nav className="result-tabs" aria-label="Result views">
        {(["output", "diagnostics", "metrics", "bytecode", "trace"] as View[]).map((item) =>
          <button key={item} className={view === item ? "active" : ""} onClick={() => setView(item)}>
            {item.toUpperCase()}
          </button>
        )}
      </nav>
      <div className="result-body">
        {transportError && <div className="error-note" role="alert">Backend: {transportError}</div>}
        {runningJob && <div className="muted-note">Executing native process…</div>}
        {!report && !runningJob && !transportError && <div className="empty-state">Run a PlusMinus program to see native output and metrics.</div>}
        {report && view === "output" && <pre>{renderOutput(report)}</pre>}
        {report && view === "diagnostics" && (
          <div>
            <div className={"result-status " + (report.ok ? "good" : "bad")}>
              {report.ok ? "EXECUTION COMPLETED" : "EXECUTION FAILED"}
            </div>
            {report.error && <pre className="diagnostic-error">{report.error}</pre>}
            {report.diagnostics.length ? report.diagnostics.map((d, i) =>
              <div key={i} className="diagnostic-line">{d.phase} · {d.line}:{d.column} · {d.message}</div>) :
              <div className="muted-note">No compiler diagnostics.</div>}
          </div>
        )}
        {response && view === "metrics" && <div className="metrics-grid">
          <Metric title="End-to-end" value={formatMetric(response.wall_ms, "ms")} />
          <Metric title="Native compilation" value={formatMetric(report?.metrics.compile_ms, "ms")} />
          <Metric title="Native execution" value={formatMetric(report?.metrics.execute_ms, "ms")} />
          <Metric title="Compiled instructions" value={formatMetric(report?.metrics.program_instructions)} />
          <Metric title="Profiled instructions" value={formatMetric(report?.metrics.executed_instructions)} />
          <Metric title="CPU time" value="not measured" />
          <Metric title="Peak RSS" value="not measured" />
          <Metric title="Exit code" value={response.exit_code === null ? "unavailable" : String(response.exit_code)} />
        </div>}
        {report && view === "bytecode" && <pre>{report.bytecode || "(No bytecode produced)"}</pre>}
        {report && view === "trace" && <TraceReplay trace={report.trace} nativeTruncated={report.trace_truncated} />}
      </div>
    </div>
  );
}

function Metric({ title, value }: { title: string; value: string }) {
  return <div className="metric"><small>{title}</small><strong>{value}</strong></div>;
}
