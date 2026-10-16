// Model menu ported from DeepSeek Harness 0.2.1-alpha.1 (packages/client/ui-model-selection ModelSelect, commit
// 5badb15009ae1756c3afe0ae0cef1faafc290ccc). Copyright (c) 2026 DeepSeek; MIT, see
// frontend/public/licenses/deepseek-harness.txt. Adapted to BRIDGE's per-conversation model-selection API. The effort
// control follows Claude Code: a chip that opens a popover with a stepped slider, built on Radix Popover and Slider.
import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type FocusEvent, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { Check, ChevronDown, X } from "lucide-react";
import { Popover, Slider } from "radix-ui";
import { api, type Effort, type ModelChoice, type ModelDirectory, type ModelSelectionView } from "../api";
import { EFFORT_NAMES } from "../modelChoice";

type Props = {
  /** The conversation the choice belongs to; null before the conversation exists. */
  sessionId: string | null;
  /** The conversation's saved choice as the session reports it. */
  current?: ModelChoice | null;
  /** Creates the conversation when a model is chosen before the first message. */
  ensureSession?: () => Promise<string>;
  disabled?: boolean;
};

const MEASURE_STYLE: CSSProperties = { visibility: "hidden", left: 0, top: 0 };
const SEARCH_FROM = 5;

/** Asks the settings dialog on this page to open at its model services. */
export const openModelSettings = () => window.dispatchEvent(new CustomEvent("bridge:open-settings", { detail: { section: "models" } }));

/** Only a complete model-selection view is used; anything else leaves the controls on the session's own choice. */
const isView = (value: unknown): value is ModelSelectionView => {
  const v = value as Partial<ModelSelectionView> | null;
  return !!v && typeof v.selection?.model === "string" && typeof v.availability?.state === "string" && typeof v.capability?.status === "string";
};

/** Case-insensitive ordered-subsequence match, prefix matches first, then catalogue order. */
function rankByName(models: string[], query: string) {
  const q = query.toLowerCase();
  if (!q) return models;
  const hits = models.filter(name => { let i = 0; for (const ch of name.toLowerCase()) if (ch === q[i]) i += 1; return i === q.length; });
  return [...hits.filter(n => n.toLowerCase().startsWith(q)), ...hits.filter(n => !n.toLowerCase().startsWith(q))];
}

/**
 * Model and thinking effort of one conversation, under the input: a model menu and an effort slider. Each change applies
 * to the next question. The slider offers only the levels the service declared for the model and is absent while they
 * are unconfirmed; a model without a declared default and no chosen level says "Provider default".
 */
export function ModelControls({ sessionId, current = null, ensureSession, disabled = false }: Props) {
  const [sid, setSid] = useState(sessionId);
  const [view, setView] = useState<ModelSelectionView | null>(null);
  const [pending, setPending] = useState<ModelChoice | null>(null);
  const [toast, setToast] = useState<{ seq: number; text: string } | null>(null);
  const toastSeq = useRef(0);
  useEffect(() => { setSid(sessionId); }, [sessionId]);
  // The effort slider needs the model's declared levels, so the conversation's full choice is read once it exists.
  useEffect(() => {
    setView(null);
    if (!sid) return;
    const controller = new AbortController();
    api.modelSelection(sid, controller.signal).then(value => { if (!controller.signal.aborted && isView(value)) setView(value); }, () => undefined);
    return () => controller.abort();
  }, [sid]);
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(null), 3200); return () => clearTimeout(timer); }, [toast]);

  const target = async () => {
    const value = sid ?? (await ensureSession?.()) ?? null;
    if (!value) throw new Error("发送第一条消息后再选择模型。");
    if (value !== sid) setSid(value);
    return value;
  };
  const save = async (choice: ModelChoice) => {
    setPending(choice);
    try { const next = await api.saveModelSelection(await target(), choice); if (isView(next)) setView(next); return true; }
    catch (failure) {
      toastSeq.current += 1;
      setToast({ seq: toastSeq.current, text: failure instanceof Error ? failure.message : "没能保存。" });
      return false;
    } finally { setPending(null); }
  };
  const selection = view?.selection ?? current;
  const unavailable = view?.availability.state === "unavailable";
  const capability = view?.capability;

  return <div className="model-controls">
    <ModelMenu selection={selection ?? null} unavailable={unavailable} pending={pending} disabled={disabled}
      onOpen={async () => { await target().catch(() => undefined); }} onChoose={(provider, model) => save({ provider_id: provider, model, effort: null })} />
    {selection && capability?.status === "supported" && capability.supported_levels.length > 0 &&
      <EffortControl levels={capability.supported_levels} fallback={capability.default_level} value={selection.effort} disabled={disabled || !!pending}
        onChange={effort => { void save({ ...selection, effort }); }} />}
    {toast && <div key={toast.seq} className="model-seat-toast" role="alert">{toast.text}</div>}
  </div>;
}

/** The model list, grouped by service, with search from five models up. Choosing a model resets its level to the declared default. */
function ModelMenu({ selection, unavailable, pending, disabled, onOpen, onChoose }: {
  selection: ModelChoice | null; unavailable: boolean; pending: ModelChoice | null; disabled: boolean;
  onOpen: () => Promise<void>; onChoose: (provider: string, model: string) => Promise<boolean>;
}) {
  const id = useId();
  const [directory, setDirectory] = useState<ModelDirectory | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "ready">("idle");
  const [loadError, setLoadError] = useState("");
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const [menuPos, setMenuPos] = useState<CSSProperties | null>(null);
  const rootRef = useRef<HTMLDivElement>(null), triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null), searchRef = useRef<HTMLInputElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const providers = directory?.providers ?? [];
  const total = providers.reduce((n, p) => n + p.models.length, 0);
  const showSearch = total >= SEARCH_FROM;
  const groups = useMemo(() => providers.map(p => ({ ...p, models: rankByName(p.models, showSearch ? query.trim() : "") })).filter(p => p.models.length), [providers, query, showSearch]);
  const visible = groups.flatMap(g => g.models.map(model => ({ provider: g.id, model, usable: g.configured })));
  const currentIndex = visible.findIndex(m => m.provider === selection?.provider_id && m.model === selection?.model);
  const active = Math.min(highlighted ?? Math.max(0, currentIndex), visible.length - 1);
  const busy = pending !== null;

  const load = () => {
    setStatus("loading"); setLoadError("");
    void Promise.all([api.models(), onOpen()]).then(([list]) => { setDirectory(list); setStatus("ready"); },
      failure => { setLoadError(failure instanceof Error ? failure.message : "模型列表读不出来。"); setStatus("ready"); });
  };
  useEffect(() => {
    if (!open) return;
    const outside = (event: MouseEvent) => {
      if (rootRef.current?.contains(event.target as Node) || menuRef.current?.contains(event.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", outside);
    return () => document.removeEventListener("mousedown", outside);
  }, [open]);
  // Placed above the trigger, right edges aligned, measured before paint and kept inside the viewport.
  useLayoutEffect(() => {
    if (!open) { setMenuPos(null); return; }
    const place = () => {
      const rect = triggerRef.current?.getBoundingClientRect();
      if (!rect) return;
      const margin = 12, w = menuRef.current?.offsetWidth ?? 0, h = menuRef.current?.offsetHeight ?? 0;
      let x = rect.right - w, y = rect.top - 8 - h;
      if (w > 0) x = Math.min(Math.max(x, margin), window.innerWidth - w - margin);
      if (h > 0) y = Math.min(Math.max(y, margin), window.innerHeight - h - margin);
      setMenuPos({ left: x, top: y });
    };
    place();
    window.addEventListener("scroll", place, true); window.addEventListener("resize", place);
    return () => { window.removeEventListener("scroll", place, true); window.removeEventListener("resize", place); };
  }, [open, status, query, directory]);
  useEffect(() => {
    if (!open || status !== "ready") return;
    if (showSearch) { searchRef.current?.focus(); return; }
    const checked = menuRef.current?.querySelector<HTMLElement>('[role="menuitemradio"][aria-checked="true"]:not([disabled])');
    (checked ?? itemRefs.current.find(i => i && !i.disabled))?.focus();
  }, [open, status, showSearch]);

  const close = (restore = false) => { setOpen(false); if (restore) queueMicrotask(() => triggerRef.current?.focus()); };
  const choose = (provider: string, model: string) => {
    if (selection?.provider_id === provider && selection.model === model) { close(true); return; }
    triggerRef.current?.focus();
    void onChoose(provider, model).then(ok => { if (ok) close(true); });
  };
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.nativeEvent.isComposing || !open) return;
    if (event.key === "Escape") { event.preventDefault(); close(true); return; }
    if (showSearch && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
      event.preventDefault();
      if (!busy && visible.length) { setHighlighted((active + (event.key === "ArrowDown" ? 1 : -1) + visible.length) % visible.length); searchRef.current?.focus(); }
      return;
    }
    if (showSearch && event.target instanceof HTMLInputElement && event.key === "Enter") {
      event.preventDefault();
      const target = visible[active];
      if (!busy && target?.usable) choose(target.provider, target.model);
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const items = itemRefs.current.filter((i): i is HTMLButtonElement => !!i && !i.disabled);
      const at = items.findIndex(i => i === document.activeElement), step = event.key === "ArrowDown" ? 1 : -1;
      items[at === -1 ? (step > 0 ? 0 : items.length - 1) : (at + step + items.length) % items.length]?.focus();
    }
  };
  const onBlur = (event: FocusEvent<HTMLDivElement>) => {
    if (event.relatedTarget instanceof Node && (rootRef.current?.contains(event.relatedTarget) || menuRef.current?.contains(event.relatedTarget))) return;
    close();
  };

  const label = unavailable ? "模型不可用" : selection?.model ?? "模型";
  itemRefs.current = [];
  let modelIndex = 0;
  return <div ref={rootRef} className="model-seat" onKeyDown={onKeyDown} onBlur={onBlur}
    onMouseDown={event => { if (event.target instanceof Element && event.target.closest("button")) event.preventDefault(); }}>
    <button ref={triggerRef} type="button" className={`model-seat-trigger${unavailable ? " model-seat-trigger--warn" : ""}`} disabled={disabled}
      aria-label={`模型：${label}`} aria-haspopup="menu" aria-expanded={open} aria-controls={open ? `${id}-menu` : undefined} aria-busy={busy}
      title="下一次提问生效" onClick={() => { if (open) close(true); else { setQuery(""); setHighlighted(null); setOpen(true); load(); } }}>
      <span className="model-seat-label">{label}</span>
      {busy && pending?.effort === null ? <span className="model-seat-dot" aria-hidden="true" /> : <ChevronDown size={12} className={`model-seat-chevron${open ? " model-seat-chevron--open" : ""}`} aria-hidden="true" />}
    </button>
    {open && createPortal(<div ref={menuRef} id={`${id}-menu`} className="model-seat-menu" style={menuPos ?? MEASURE_STYLE}
      role="group" aria-label="选择模型" aria-busy={status === "loading" || busy}>
      {showSearch && <div className="model-seat-search">
        <input ref={searchRef} type="text" role="searchbox" aria-label="搜索模型" placeholder="搜索模型" value={query} readOnly={busy}
          aria-controls={`${id}-models`} aria-activedescendant={active < 0 ? undefined : `${id}-model-${active}`}
          onChange={e => { setQuery(e.target.value); setHighlighted(0); }} />
        {query && <button type="button" aria-label="清除搜索" disabled={busy} onClick={() => { setQuery(""); setHighlighted(0); searchRef.current?.focus(); }}><X size={12} /></button>}
      </div>}
      {status === "loading" && <div className="model-seat-status">正在读取…</div>}
      {loadError && <div className="model-seat-error"><span>{loadError}</span><button type="button" onClick={load}>重试</button></div>}
      <div id={`${id}-models`} className="model-seat-groups" role="menu" aria-label="模型" hidden={!groups.length}>
        {groups.map(group => <section key={group.id} aria-label={group.name}>
          <h4>{group.name}</h4>
          {group.models.map(model => {
            const index = modelIndex++;
            const chosen = selection?.provider_id === group.id && selection.model === model;
            return <button key={model} ref={node => { itemRefs.current[index] = node; }} type="button" role="menuitemradio" aria-checked={chosen}
              id={`${id}-model-${index}`} tabIndex={showSearch ? -1 : 0} onFocus={() => setHighlighted(index)}
              className={`model-seat-option${index === active ? " model-seat-option--active" : ""}`} disabled={busy || !group.configured}
              title={group.configured ? model : `${model}（服务未配置密钥）`}
              onMouseMove={busy || index === active ? undefined : () => { if (showSearch) setHighlighted(index); else itemRefs.current[index]?.focus(); }}
              onClick={() => choose(group.id, model)}>
              <span className="model-seat-name">{model}</span>
              <span className="model-seat-check">{pending?.provider_id === group.id && pending.model === model ? <span className="model-seat-dot" /> : chosen ? <Check size={14} /> : null}</span>
            </button>;
          })}
        </section>)}
      </div>
      {status === "ready" && !groups.length && <div className="model-seat-status" role="status">{total ? "没有匹配的模型" : "还没有可用的模型"}</div>}
      <button type="button" className="model-seat-manage" onClick={() => { close(); openModelSettings(); }}>管理模型</button>
    </div>, document.body)}
  </div>;
}

/**
 * Effort chip and its popover, as in Claude Code: the chip shows the level; the popover holds a stepped slider from
 * faster to deeper with one stop per declared level, the declared default marked, saved when released. A model without
 * a declared default and no chosen level reads "Provider default" with no thumb until the slider is touched.
 */
function EffortControl({ levels, fallback, value, disabled, onChange }: {
  levels: Effort[]; fallback: Effort | null; value: Effort | null; disabled: boolean; onChange: (effort: Effort) => void;
}) {
  const [draft, setDraft] = useState<number | null>(null);
  const index = levels.indexOf(value as Effort);
  const shown = draft ?? (index >= 0 ? index : null);
  const text = shown === null ? "Provider default" : EFFORT_NAMES[levels[shown]];
  const chip = index >= 0 ? EFFORT_NAMES[levels[index]] : "Provider default";
  const stop = (i: number) => `${levels.length < 2 ? 50 : (i / (levels.length - 1)) * 100}%`;
  const defaultAt = fallback ? levels.indexOf(fallback) : -1;
  return <Popover.Root onOpenChange={open => { if (!open) setDraft(null); }}>
    <Popover.Trigger asChild>
      <button type="button" className="effort-chip" disabled={disabled} aria-label={`Effort: ${chip}`} title="下一次提问生效">{chip}</button>
    </Popover.Trigger>
    <Popover.Portal>
      <Popover.Content className="effort-pop" side="top" align="end" sideOffset={10} collisionPadding={12}>
        <div className="effort-pop-head"><span>Effort</span><b>{text}</b></div>
        <div className="effort-pop-ends" aria-hidden="true"><span>Faster</span><span>Smarter</span></div>
        <Slider.Root className="effort-pop-slider" min={0} max={Math.max(1, levels.length - 1)} step={1} disabled={disabled}
          value={[shown ?? 0]} data-unset={shown === null ? "" : undefined}
          onValueChange={([next]) => setDraft(next)}
          onValueCommit={([next]) => { setDraft(null); if (next !== index) onChange(levels[next]); }}>
          <Slider.Track className="effort-pop-track">
            {shown !== null && <Slider.Range className="effort-pop-range" />}
            {levels.map((level, i) => <span key={level} className={`effort-pop-stop${i === defaultAt ? " effort-pop-stop--default" : ""}`} style={{ left: stop(i) }} />)}
          </Slider.Track>
          <Slider.Thumb className="effort-pop-thumb" aria-label="Effort" aria-valuetext={text} />
        </Slider.Root>
        {defaultAt >= 0 && <div className="effort-pop-marks" aria-hidden="true"><span style={{ left: stop(defaultAt) }}>Default</span></div>}
      </Popover.Content>
    </Popover.Portal>
  </Popover.Root>;
}
