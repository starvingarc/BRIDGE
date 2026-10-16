import { useState } from "react";
import { CultureDish, artFor } from "./StageDish";
import { ROMAN, STAGE_NAMES, stageOf, wallGroup, type WallGroup } from "./stages";
import type { Protocol, QueueItem } from "./types";
import { greeting } from "./greeting";

const STATUS: Record<string, { label: string; tone: string }> = {
  lead: { label: "有新线索", tone: "warn" }, live: { label: "分化中", tone: "live" }, done: { label: "已评估", tone: "ok" },
  frozen: { label: "已冻存", tone: "ok" }, grafted: { label: "已移植", tone: "ok" }, draft: { label: "草稿", tone: "draft" },
};
const statusOf = (p: Protocol) => p.lead ? STATUS.lead : p.state === "draft" ? STATUS.draft : p.state === "frozen" ? STATUS.frozen
  : p.state === "grafted" ? STATUS.grafted : wallGroup(p) === "done" ? STATUS.done : STATUS.live;

type Props = {
  userName: string; protocols: Protocol[]; queue: QueueItem[]; onOpen: (id: string) => void;
  onDecide?: (id: string, decision: "approve" | "decline") => Promise<void>;
  /** Starts a new protocol from the empty state; absent when protocols cannot be created here. */
  onCreate?: () => void;
};

export function Incubator({ userName, protocols, queue, onOpen, onDecide, onCreate }: Props) {
  const [filter, setFilter] = useState<"all" | WallGroup>("all");
  const [queueState, setQueueState] = useState<Record<string, "running" | "done" | "later">>({});
  const [queueError, setQueueError] = useState("");
  const decide = async (id: string, decision: "approve" | "decline") => {
    setQueueError("");
    setQueueState(s => ({ ...s, [id]: decision === "approve" ? "running" : "later" }));
    if (!onDecide) return;
    try { await onDecide(id, decision); }
    catch (failure) { setQueueState(s => { const next = { ...s }; delete next[id]; return next; }); setQueueError(failure instanceof Error ? failure.message : "没有提交成功，请重试。"); }
  };
  const visible = protocols.filter(p => filter === "all" || wallGroup(p) === filter);
  const todo = protocols.filter(p => p.state === "differentiating" && p.day < p.totalDays && p.today.trim());
  const leads = protocols.filter(p => p.lead);
  return <section className="wb-wall" aria-labelledby="wb-wall-title">
    <header className="wb-hello">
      <h1>{greeting()}，{userName}</h1>
      <p>{todo.length + leads.length ? `今天有 ${todo.length + leads.length} 件事` : "今天没有待办"}</p>
    </header>
    <ul className="wb-today" aria-label="今天">
      {todo.map(p => { const s = stageOf(p); return <li key={p.id}><i className="wb-dot" /><b>{`D${p.day} · ${ROMAN[s.index]}`}</b>{p.name} · {p.today}</li>; })}
      {leads.map(p => <li key={`lead-${p.id}`}><i className="wb-dot wb-dot--warn" /><b>线索</b>{p.name} · {p.lead}</li>)}
    </ul>
    <div className="wb-section">
      <h2 id="wb-wall-title">培养箱</h2>
      <div className="wb-filters" role="group" aria-label="筛选">
        {(["all", "live", "done", "grafted"] as const).map(key =>
          <button key={key} aria-pressed={filter === key} onClick={() => setFilter(key)}>{{ all: "全部", live: "分化中", done: "已完成", grafted: "已移植" }[key]}</button>)}
      </div>
    </div>
    {protocols.length === 0 && <div className="wb-empty">
      <h2>从一份方案开始</h2>
      <p>上传分化方案，BRIDGE 会把它画成方案图，核对确认后就记下这次实验。</p>
      {onCreate && <button className="wb-run" onClick={onCreate}>新建方案</button>}
    </div>}
    <div className="wb-cards">
      {visible.map(p => {
        const stage = stageOf(p), status = statusOf(p);
        return <button key={p.id} className="wb-card" onClick={() => onOpen(p.id)} aria-label={`打开${p.name}，${stage.tag}，${stage.name}`}>
          <span className="wb-card-top"><span className="wb-stage-tag">{stage.tag}</span><span className={`wb-pill wb-pill--${status.tone}`}>{status.label}</span></span>
          <CultureDish art={artFor(p)} keyId={p.id} live={p.state === "differentiating" || p.state === "expanding"} />
          <span className="wb-card-name">{p.name}</span>
          <span className="wb-card-stage">{stage.name}</span>
          <span className="wb-progress" aria-hidden="true">
            {[1, 2, 3, 4].map(k => <i key={k} title={`Stage ${ROMAN[k]} ${STAGE_NAMES[k]}`}
              className={p.state === "draft" ? "" : k < stage.index || (p.state !== "differentiating" && p.state !== "expanding" && k <= stage.index) ? "done" : k === stage.index ? "now" : ""} />)}
          </span>
          <span className="wb-card-today">{p.today}</span>
        </button>;
      })}
    </div>
    {queue.length > 0 && <>
      <div className="wb-section"><h2>等你确认</h2><span className="wb-muted">确认后在沙箱中运行</span></div>
      <ul className="wb-queue">
        {queue.map(item => <li key={item.id} className={queueState[item.id] === "later" ? "wb-queue--later" : ""}>
          <div>{item.title}<small>{item.context}</small></div>
          <div><small>{item.tier === "exploratory" ? "探索性" : "正式工具"}</small>{item.eta}</div>
          <div className="wb-queue-actions">
            <button className="wb-run" disabled={!!queueState[item.id] && queueState[item.id] !== "later"}
              onClick={() => void decide(item.id, "approve")}>
              {queueState[item.id] === "running" ? "已提交" : "运行"}</button>
            <button onClick={() => void decide(item.id, "decline")}>{onDecide ? "不需要" : "稍后"}</button>
          </div>
        </li>)}
      </ul>
      {queueError && <p className="wb-error" role="alert">{queueError}</p>}
    </>}
  </section>;
}
