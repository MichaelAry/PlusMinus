"""Consistent, honest presentation of native PlusMinus run results.

Report metrics come from the actual C++ process and sampling, never estimates.
This module is Qt-independent so GUI behavior can be regression-tested.
"""


def _measured(value, unit="", precision=2):
    if value is None or isinstance(value, bool):
        return "not measured"
    if isinstance(value, (float, int)):
        return f"{value:.{precision}f}{(' ' + unit) if unit else ''}"
    return str(value)


def render_output(report):
    """Return visible output even for empty stdout and a numeric zero return."""
    stdout = str(report.get("output") or "")
    result = report.get("result")
    lines = [stdout.rstrip("\n")] if stdout else ["(No stdout produced)"]
    if result is not None and result != "":
        lines.append(f"Return value: {result}")
    if not report.get("ok", False):
        lines.append("\nExecution failed — see diagnostics and run details.")
    return "\n".join(lines)


def render_details(report, mode="Run"):
    metrics = report.get("metrics") or {}
    samples = metrics.get("samples") or []
    opcode_hits = metrics.get("opcode_hits") or {}
    lines = [
        "EXECUTION REPORT",
        "─────────────────────────────────",
        f"Operation                 {mode}",
        f"Status                    {'SUCCESS' if report.get('ok') else 'FAILED'}",
        f"End-to-end wall time      {_measured(report.get('ms'), 'ms')}",
        f"Native compile time       {_measured(metrics.get('compile_ms'), 'ms')}",
        f"Native execution time     {_measured(metrics.get('execute_ms'), 'ms')}",
        f"Process CPU time          {_measured(metrics.get('cpu_ms'), 'ms')}",
        f"Sampled peak process RSS  {_measured(metrics.get('peak_rss_mb'), 'MB')}",
        f"Sampled max threads       {_measured(metrics.get('peak_threads'), precision=0)}",
        f"Compiled VM instructions  {_measured(metrics.get('program_instructions'), precision=0)}",
        f"Executed VM instructions  {_measured(metrics.get('executed_instructions'), precision=0)}",
        f"Measured opcode types     {len(opcode_hits) if opcode_hits else 'not measured'}",
        f"Resource samples          {len(samples)}",
        f"Trace events              {len(report.get('trace') or [])}",
    ]
    if report.get("trace_truncated"):
        lines.append("Trace                    truncated (limit reached)")
    if not samples:
        lines.append("")
        lines.append("Resource sampling can miss short-lived programs; unavailable is not zero.")
    if report.get("error"):
        lines.extend(("", "DIAGNOSTICS", str(report["error"])))
    return "\n".join(lines)
