import type { Preview, PreviewRequest } from "./sampling";
import type { PreviewAnswer, PreviewMessage } from "./preview.worker";

/** One running and at most one queued request, with no GUI work in the worker. */
export class PlotPreview {
  private revision = 0;
  private running: { revision: number; cancelled: boolean } | undefined;
  private pending: PreviewRequest | undefined;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private worker = new Worker(new URL("./preview.worker.ts", import.meta.url), { type: "module" });

  constructor(apply: (preview: Preview) => void, error: (message: string) => void) {
    this.worker.onmessage = ({ data }: MessageEvent<PreviewAnswer>) => {
      if (data.revision !== this.running?.revision) return;
      this.running = undefined;
      if (data.revision === this.revision) {
        if (data.preview) apply(data.preview);
        else if (data.error) error(data.error);
      }
      this.start();
    };
    this.worker.onerror = event => {
      this.running = undefined;
      error(event.message || "Preview worker stopped");
    };
  }

  schedule(request: Omit<PreviewRequest, "revision">, delay: number) {
    const revision = ++this.revision;
    this.pending = { ...request, revision };
    if (this.running && !this.running.cancelled) {
      this.running.cancelled = true;
      this.send({ cancel: this.running.revision });
    }
    if (delay === 60 || this.timer === undefined) {
      clearTimeout(this.timer);
      this.timer = setTimeout(() => {
        this.timer = undefined;
        this.start();
      }, delay);
    }
  }

  dispose() {
    clearTimeout(this.timer);
    this.worker.terminate();
  }

  private send(message: PreviewMessage) { this.worker.postMessage(message); }

  private start() {
    if (this.timer !== undefined || this.running !== undefined || !this.pending) return;
    this.running = { revision: this.pending.revision, cancelled: false };
    this.send({ request: this.pending });
    this.pending = undefined;
  }
}
