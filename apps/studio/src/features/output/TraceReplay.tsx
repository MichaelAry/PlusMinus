import { useEffect, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { TraceEvent } from "../../api/contracts";

export const TRACE_LIMIT = 5000;
export function traceWindow(all: TraceEvent[], nativeTruncated: boolean) {
  return { events: all.slice(0, TRACE_LIMIT), truncated: nativeTruncated || all.length > TRACE_LIMIT };
}
export function clampTraceIndex(index: number, count: number) {
  return Math.max(0, Math.min(count-1, Math.round(Number.isFinite(index) ? index : 0)));
}

export function TraceReplay({ trace, nativeTruncated }: {
  trace: TraceEvent[]; nativeTruncated: boolean;
}) {
  const { events, truncated } = traceWindow(trace, nativeTruncated);
  const [selected, setSelected] = useState(0);
  const parent = useRef<HTMLDivElement>(null);
  const list = useVirtualizer({
    count: events.length, getScrollElement: () => parent.current,
    estimateSize: () => 28, overscan: 15,
  });
  useEffect(() => setSelected(0), [trace]);
  useEffect(() => {
    if (events.length) list.scrollToIndex(selected, { align: "center" });
  }, [selected, events.length]);
  const current = events[selected];
  const move = (value: number) => setSelected(clampTraceIndex(value, events.length));

  if (!events.length) return <div className="empty-state">No recorded trace. Use F7 to capture a post-execution trace.</div>;
  return <div className="trace-replay">
    <div className="muted-note">
      Recorded post-execution trace · {events.length} events
      {truncated ? " · capped at 5,000 events" : ""}. Not a live debugger.
    </div>
    <div className="trace-controls">
      <button aria-label="Previous trace event" disabled={selected === 0} onClick={() => move(selected-1)}>Previous</button>
      <input aria-label="Trace event position" type="range" min={0} max={events.length-1}
        value={selected} onChange={e => move(Number(e.target.value))}/>
      <button aria-label="Next trace event" disabled={selected >= events.length-1} onClick={() => move(selected+1)}>Next</button>
      <span>Event {selected+1} / {events.length}</span>
    </div>
    <div className="trace-selected" role="status">
      <strong>IP {current.ip} · {current.opcode}</strong>
      <span>VM thread #{current.thread}</span>
      <span>Stack depth {current.stack_depth}</span>
    </div>
    <div className="trace-timeline" ref={parent} role="list" aria-label="Recorded trace events">
      <div style={{height:list.getTotalSize(),position:"relative"}}>
        {list.getVirtualItems().map(row => {
          const event=events[row.index],active=selected===row.index;
          return <button role="listitem" key={row.index} className={"trace-event"+(active?" active":"")}
            style={{position:"absolute",top:0,left:0,width:"100%",height:row.size,
              transform:"translateY("+row.start+"px)"}}
            aria-current={active?"step":undefined}
            onClick={() => move(row.index)}>
            <span>#{row.index+1}</span><span>IP {event.ip}</span>
            <strong>{event.opcode}</strong>
            <span>thread {event.thread}</span>
            <span>depth {event.stack_depth}</span>
          </button>;
        })}
      </div>
    </div>
  </div>;
}
