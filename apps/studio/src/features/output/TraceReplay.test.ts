import { describe,expect,it } from "vitest";
import { TRACE_LIMIT, clampTraceIndex, traceWindow } from "./TraceReplay";
describe("post-execution trace replay",()=>{
  const event={ip:0,opcode:"PushConst",thread:0,stack_depth:1};
  it("enforces native 5000 event upper bound",()=>{
    const all=Array.from({length:TRACE_LIMIT+7},()=>event);
    const replay=traceWindow(all,false);
    expect(replay.events).toHaveLength(TRACE_LIMIT);
    expect(replay.truncated).toBe(true);
  });
  it("retains explicit native truncation marker",()=>{
    expect(traceWindow([event],true).truncated).toBe(true);
  });
  it("clamps Prev/Next to valid boundaries",()=>{
    expect(clampTraceIndex(-1,3)).toBe(0);
    expect(clampTraceIndex(5,3)).toBe(2);
    expect(clampTraceIndex(Number.NaN,3)).toBe(0);
  });
});
