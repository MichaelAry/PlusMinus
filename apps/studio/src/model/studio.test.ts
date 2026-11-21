import { describe, expect, it } from "vitest";
import { useStudio } from "./studio";

describe("document lifecycle", () => {
  it("retains dirty state if edits occur during an asynchronous save", () => {
    useStudio.getState().open({ path: "race.pm", source: "initial", digest: "old" });
    useStudio.getState().edit("race.pm", "first");
    useStudio.getState().edit("race.pm", "second");
    useStudio.getState().saved("race.pm", {
      path: "race.pm", source: "first", digest: "hash-of-first",
    });
    const doc = useStudio.getState().documents.find((d) => d.id === "race.pm");
    expect(doc?.source).toBe("second");
    expect(doc?.dirty).toBe(true);
    expect(doc?.digest).toBe("hash-of-first");
  });

  it("provides a new editor identity when changing the workspace", () => {
    useStudio.getState().setWorkspace("first", []);
    const before = useStudio.getState().activeId;
    useStudio.getState().edit(before, "modified");
    useStudio.getState().setWorkspace("second", []);
    const state = useStudio.getState();
    expect(state.activeId).not.toBe(before);
    expect(state.documents[0].source).not.toBe("modified");
    expect(state.documents[0].dirty).toBe(false);
  });
});
