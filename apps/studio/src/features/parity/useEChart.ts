import { useEffect, useRef } from "react";
import type { ECharts, EChartsOption } from "echarts";

// A single chart instance per panel. Frequent telemetry updates only change
// the option data; no expensive canvas teardown / reinitialization.
export function useEChart(option: EChartsOption | null) {
  const host=useRef<HTMLDivElement>(null);
  const chart=useRef<ECharts|null>(null);
  const latest=useRef(option);
  latest.current=option;
  useEffect(()=>{
    let alive=true;
    let observer:ResizeObserver|null=null;
    void import("echarts").then(module=>{
      if(!alive||!host.current)return;
      const instance=module.init(host.current);
      chart.current=instance;
      if(latest.current)instance.setOption(latest.current,{notMerge:true,lazyUpdate:true});
      if(typeof ResizeObserver!=="undefined"){
        observer=new ResizeObserver(()=>instance.resize());
        observer.observe(host.current);
      }
    });
    return()=>{
      alive=false;observer?.disconnect();chart.current?.dispose();chart.current=null;
    };
  },[]);
  useEffect(()=>{
    if(option&&chart.current)chart.current.setOption(option,{notMerge:true,lazyUpdate:true});
  },[option]);
  return host;
}
