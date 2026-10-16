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

export function ResearcherMarkdownText() {
  return <Suspense fallback={<span className="message-loading">正在读取说明…</span>}>
    <MarkdownTextImpl researcher />
  </Suspense>;
}
