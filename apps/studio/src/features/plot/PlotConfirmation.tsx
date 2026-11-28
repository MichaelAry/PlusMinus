import { useLayoutEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { usePlot } from "./store";

export function PlotConfirmation() {
  const question = usePlot(state => state.question);
  const dialog = useRef<HTMLDialogElement>(null);
  useLayoutEffect(() => {
    if (!question) return;
    const current = dialog.current;
    const owner = question.owner.defaultView;
    const cancel = () => question.resolve("cancel");
    if (current && !current.open) current.showModal();
    owner?.addEventListener("pagehide", cancel);
    return () => {
      owner?.removeEventListener("pagehide", cancel);
      current?.close();
    };
  }, [question]);
  if (!question) return null;
  const { owner, resolve } = question;
  return createPortal(
    <dialog ref={dialog} className="plot-confirm" aria-labelledby="plot-confirm-title"
      onCancel={event => { event.preventDefault(); resolve("cancel"); }}>
      <h2 id="plot-confirm-title">Save plot changes?</h2>
      <p>The current plot has unsaved changes.</p>
      <div>
        <button onClick={() => resolve("save")}>Save</button>
        <button onClick={() => resolve("discard")}>Discard</button>
        <button onClick={() => resolve("cancel")} autoFocus>Cancel</button>
      </div>
    </dialog>,
    owner.body,
  );
}
