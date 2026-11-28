import { calculate, type Preview, type PreviewRequest } from "./sampling";

export type PreviewMessage = { request: PreviewRequest } | { cancel: number };
export type PreviewAnswer = { revision: number; preview?: Preview; error?: string };

let cancelled = -1;

// Yield between sample blocks so cancellation can reach the worker without
// paying the minimum delay of nested browser timers.
const channel = new MessageChannel();
let resume: (() => void) | undefined;
channel.port1.onmessage = () => {
  const continueJob = resume;
  resume = undefined;
  continueJob?.();
};
function yieldToMessages() {
  return new Promise<void>(resolve => {
    resume = resolve;
    channel.port2.postMessage(null);
  });
}
self.onmessage = ({ data }: MessageEvent<PreviewMessage>) => {
  if ("cancel" in data) cancelled = Math.max(cancelled, data.cancel);
  else void preview(data.request);
};

async function preview(request: PreviewRequest) {
  const { revision } = request;
  let answer: PreviewAnswer = { revision };
  try {
    const job = calculate(request);
    while (revision > cancelled) {
      const block = job.next();
      if (block.done) {
        answer = { revision, preview: block.value };
        break;
      }
      await yieldToMessages();
    }
  } catch (error) {
    answer = { revision, error: String(error) };
  }
  self.postMessage(answer);
}
