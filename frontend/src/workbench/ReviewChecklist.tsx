import { ROMAN } from "./stages";
import type { Protocol, ReviewItem } from "./types";

const ORDER: ReviewItem[] = ["source_review", "total_days", "stages", "operations"];

/**
 * Whole-version items an imported draft must have checked, one by one, before it can be confirmed.
 * The source item unlocks only after the original text has been shown.
 */
export function ReviewChecklist({ protocol, sourceSeen, busy, onClear, onOpenSource }: {
  protocol: Protocol; sourceSeen: boolean; busy: boolean; onClear: (item: ReviewItem) => void;
  /** Opens the original text beside the flow; the source item can be ticked once it has been seen. */
  onOpenSource?: () => void;
}) {
  const pending = new Set(protocol.source?.review ?? []);
  if (!pending.size) return null;
  const operations = protocol.operations ?? [];
  const detail: Record<ReviewItem, { label: string; note: string; blocked?: string }> = {
    source_review: { label: "对照原文看过整份方案", note: "包括原文里有、方案图上没有的内容",
      blocked: sourceSeen ? undefined : "先打开原文" },
    total_days: { label: "总天数", note: protocol.source?.totalDaysSet ? `${protocol.totalDays} 天` : "原文未写明",
      blocked: protocol.source?.totalDaysSet ? undefined : "先填写总天数" },
    stages: { label: "阶段划分", note: protocol.stages?.length
      ? protocol.stages.map(s => `${ROMAN[s.index]} D${s.start}–${s.end}`).join(" · ") : "原文未写明，按默认阶段显示" },
    operations: { label: `操作步骤（${operations.length} 项）`, note: operations.length
      ? operations.map(o => `${o.day === null ? "日期未写明" : `D${o.day}`} ${o.note}`).join("；") : "没有登记的操作" },
  };
  return <section className="wb-review" aria-label="整份方案待核对">
    <h2>整份方案待核对 <span className="wb-muted">还有 {pending.size} 项</span></h2>
    <ul>
      {ORDER.filter(item => pending.has(item)).map(item => {
        const d = detail[item];
        return <li key={item}>
          <span><b>{d.label}</b><small>{d.note}</small></span>
          {item === "source_review" && d.blocked && onOpenSource
            ? <button className="wb-chip" disabled={busy} onClick={onOpenSource}>打开原文</button>
            : <button className="wb-chip" disabled={busy || !!d.blocked} title={d.blocked} onClick={() => onClear(item)}
              aria-label={`已核对：${d.label}`}>{d.blocked ?? "已核对"}</button>}
        </li>;
      })}
    </ul>
  </section>;
}
