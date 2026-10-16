import { Fragment, useEffect, useMemo, useRef } from "react";
import type { SourceQuote, SourceView } from "./types";

type Mark = { from: number; to: number; quote: SourceQuote };

const KIND_LABEL: Record<SourceQuote["kind"], string> = { reagent: "试剂", total: "总天数", stage: "阶段", operation: "操作" };
const PRIORITY: Record<SourceQuote["kind"], number> = { reagent: 0, total: 1, stage: 2, operation: 3 };

/** Non-overlapping highlight ranges in one segment; a reagent wins over a stage or operation quoting the same words. */
function marksFor(text: string, quotes: SourceQuote[]): Mark[] {
  const found: Mark[] = [];
  for (const quote of [...quotes].sort((a, b) => PRIORITY[a.kind] - PRIORITY[b.kind])) {
    const from = quote.text ? text.indexOf(quote.text) : -1;
    if (from < 0) continue;
    const to = from + quote.text.length;
    if (!found.some(m => from < m.to && to > m.from)) found.push({ from, to, quote });
  }
  return found.sort((a, b) => a.from - b.from);
}

/**
 * The uploaded document beside its protocol flow: every value the import took from the text is highlighted,
 * reagent quotes link to their capsule, and questions the text leaves open are listed first.
 */
export function SourcePane({ source, activeReagent, onPickReagent, onSeen, onClose }: {
  source: SourceView | null | undefined; activeReagent: string | null; onPickReagent: (name: string) => void; onSeen: () => void;
  onClose: () => void;
}) {
  const active = useRef<HTMLElement>(null);
  useEffect(() => { if (source) onSeen(); }, [source, onSeen]);
  useEffect(() => { active.current?.scrollIntoView({ block: "center", behavior: "smooth" }); }, [activeReagent]);
  const segments = useMemo(() => source?.segments.map(s => ({ ...s, marks: marksFor(s.text, source.quotes) })) ?? [], [source]);
  const close = <button className="wb-link wb-source-close" onClick={onClose}>收起</button>;
  if (source === undefined) return <aside className="wb-source" aria-label="方案原文">{close}<p className="wb-muted" role="status">正在读取原文…</p></aside>;
  if (source === null) return <aside className="wb-source" aria-label="方案原文">{close}<p className="wb-muted">这一版没有可读取的原文记录。</p></aside>;
  return <aside className="wb-source" aria-label="方案原文">
    <header className="wb-source-head">
      <h2>原文</h2>
      <span className={source.compiled ? "wb-chip" : "wb-chip wb-chip--warn"}>{source.compiled ? "已转成方案图" : "转换未完成"}</span>
      {source.needsInput && <span className="wb-chip wb-chip--warn">原文有缺项</span>}
      {close}
    </header>
    {source.questions.length > 0 && <section className="wb-source-questions" aria-label="原文没写清的地方">
      <h3>原文没写清的地方</h3>
      <ul>{source.questions.map(q => <li key={q}>{q}</li>)}</ul>
    </section>}
    {segments.map(segment => <section key={segment.id} className="wb-source-segment" aria-label={`${segment.label} ${segment.location}`}>
      <p className="wb-muted">{segment.label} · {segment.location}</p>
      <p className="wb-source-text">{segment.marks.map((mark, i) => {
        const before = segment.text.slice(i ? segment.marks[i - 1].to : 0, mark.from), words = segment.text.slice(mark.from, mark.to);
        const on = mark.quote.kind === "reagent" && mark.quote.name === activeReagent;
        return <Fragment key={mark.from}>{before}
          {mark.quote.kind === "reagent"
            ? <mark ref={on ? active : undefined} className={`wb-quote wb-quote--reagent${on ? " wb-quote--on" : ""}`} role="button" tabIndex={0}
                aria-label={`原文中的 ${mark.quote.name}：${words}`} aria-current={on || undefined}
                onClick={() => onPickReagent(mark.quote.name!)} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPickReagent(mark.quote.name!); } }}>{words}</mark>
            : <mark className={`wb-quote wb-quote--${mark.quote.kind}`} title={KIND_LABEL[mark.quote.kind]}>{words}</mark>}
        </Fragment>;
      })}{segment.text.slice(segment.marks.at(-1)?.to ?? 0)}</p>
    </section>)}
    <p className="wb-muted wb-source-note">高亮只说明这些字出现在原文里，不说明它们对应得对。请逐项核对。</p>
  </aside>;
}
