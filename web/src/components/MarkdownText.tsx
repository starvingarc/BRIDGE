import { lazy, Suspense } from "react";

const MarkdownTextImpl = lazy(() =>
  import("./MarkdownTextImpl").then((module) => ({ default: module.MarkdownTextImpl })),
);

export function MarkdownText() {
  return (
    <Suspense fallback={<span className="message-loading">Loading message…</span>}>
      <MarkdownTextImpl />
    </Suspense>
  );
}
