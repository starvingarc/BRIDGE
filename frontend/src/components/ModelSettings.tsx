// Models settings section ported from DeepSeek Harness 0.2.1-alpha.1 (packages/client/ui-settings-models ModelsSection,
// ProviderEditor, CustomProviderCard and EditorFooter; commit 5badb15009ae1756c3afe0ae0cef1faafc290ccc).
// Copyright (c) 2026 DeepSeek; MIT, see frontend/public/licenses/deepseek-harness.txt.
// Adapted to BRIDGE's provider API (one directory of shared and personal providers, catalogue read, connection test,
// effort capability refresh) and BRIDGE's look; controls are the Radix primitives assistant-ui already ships.
import { useEffect, useId, useRef, useState } from "react";
import { Check, ChevronRight, Plus, X } from "lucide-react";
import { AlertDialog, Checkbox, Collapsible, Tabs } from "radix-ui";
import { api, type ModelDirectory, type ModelProvider, type ProviderInput } from "../api";
import { EFFORT_NAMES } from "../modelChoice";
import { apiKeyFailure } from "./modelKeyValidation";

/** Providers the catalogue mode can add: a known address and tool protocol, so only the key and models remain. */
const CATALOG = [
  { id: "deepseek", name: "DeepSeek", base_url: "https://api.deepseek.com", action_protocol: "deepseek_tools" },
  { id: "openai", name: "OpenAI", base_url: "https://api.openai.com/v1", action_protocol: "json" },
];
const ROUTE = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/;
const normalizeUrl = (url: string) => url.trim().replace(/\/+$/, "");
const label = (p: { id: string; name: string }) => p.name && p.name !== p.id ? `${p.name} (${p.id})` : p.id;

type AddMode = "catalog" | "custom";
type Busy = (busy: boolean) => void;

/**
 * Models settings: one card per provider with its key state, models and their declared effort; one editor card at a
 * time; a single add entry whose card switches between a catalogue provider and a custom model API; removal behind a
 * confirmation. Choosing a conversation's model happens at the input, not here.
 */
export function ModelSettings({ onBusyChange }: { embedded?: boolean; onBusyChange?: Busy } = {}) {
  const addId = useId();
  const alive = useRef(true);
  const [directory, setDirectory] = useState<ModelDirectory | null>(null);
  const [loadError, setLoadError] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [addMode, setAddMode] = useState<AddMode>("catalog");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ModelProvider | null>(null);
  const [deleteFailure, setDeleteFailure] = useState("");
  const [checks, setChecks] = useState<Record<string, { ok: boolean; at: string | null; message: string }>>({});
  // The settings window is a native modal dialog in the top layer; the confirmation must render inside it to be seen.
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => { onBusyChange?.(busy); }, [busy, onBusyChange]);
  const load = () => {
    setLoadError("");
    api.models().then(value => { if (alive.current) setDirectory(value); },
      failure => { if (alive.current) setLoadError(failure instanceof Error ? failure.message : "读取失败"); });
  };
  useEffect(load, []);

  const closeEditors = () => { setEditing(null); setAddOpen(false); };
  const savedAs = (value: ModelDirectory, provider: { id: string; name: string }) => {
    setDirectory(value); closeEditors(); setSaved(label(provider));
  };
  const refresh = async (provider: ModelProvider) => {
    setBusy(true);
    try {
      const result = await api.refreshCapabilities(provider.id);
      if (!alive.current) return;
      setChecks(all => ({ ...all, [provider.id]: { ok: result.ok, at: result.checked_at, message: result.message } }));
      if (result.ok) setDirectory(value => value && { ...value, providers: value.providers.map(p => p.id === provider.id ? { ...p, capabilities: result.capabilities } : p) });
    } catch (failure) {
      if (alive.current) setChecks(all => ({ ...all, [provider.id]: { ok: false, at: null, message: failure instanceof Error ? failure.message : "" } }));
    } finally { if (alive.current) setBusy(false); }
  };
  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setBusy(true); setDeleteFailure("");
    try { const value = await api.deleteProvider(deleteTarget.id); if (alive.current) { setDirectory(value); setDeleteTarget(null); } }
    catch (failure) { if (alive.current) setDeleteFailure(failure instanceof Error ? failure.message : "删除失败"); }
    finally { if (alive.current) setBusy(false); }
  };

  if (loadError && !directory) return <div className="models-section">
    <p className="models-error" role="alert">{`读取失败：${loadError}`}</p>
    <button type="button" className="models-secondary" onClick={load}>重新读取配置</button>
  </div>;

  const providers = directory?.providers ?? [];
  const taken = providers.map(p => p.id);
  const catalogLeft = CATALOG.filter(c => !taken.includes(c.id));
  return <div className="models-section" ref={root}>
    <h3 className="models-title">模型</h3>
    <p className="models-intro">填入各提供商的 API 密钥即可使用其模型。每段对话用哪个模型，在对话输入框右下角选择。</p>
    {saved && <p className="models-saved" role="status" aria-live="polite">已保存 {saved}。</p>}
    {!directory && <p className="models-hint" role="status">正在读取…</p>}
    <ul className="models-rows" aria-label="已配置的提供商">
      {providers.map(provider => {
        const open = !addOpen && editing === provider.id;
        const check = checks[provider.id];
        return <li key={provider.id} className="models-card">
          <div className="models-head">
            <span className="models-identity">
              <span className="models-name">{provider.name || provider.id}</span>
              {provider.shared && <span className="models-tag">共享</span>}
              <span className={`models-dot ${provider.has_api_key ? "models-dot--ok" : "models-dot--missing"}`} role="img"
                aria-label={provider.has_api_key ? "API 密钥已配置" : "API 密钥缺失"} title={provider.has_api_key ? "API 密钥已配置" : "API 密钥缺失"} />
            </span>
            <span className="models-actions">
              <button type="button" className="models-secondary" disabled={busy || !provider.configured} title="从服务读取各模型支持的 effort"
                onClick={() => void refresh(provider)}>刷新能力</button>
              {provider.editable && <button type="button" className="models-secondary" aria-label={`编辑 ${label(provider)}`} disabled={busy}
                onClick={() => { setSaved(null); setAddOpen(false); setEditing(open ? null : provider.id); }}>编辑</button>}
              {!provider.shared && <button type="button" className="models-danger" aria-label={`删除 ${label(provider)}`} disabled={busy}
                onClick={() => { setSaved(null); setDeleteFailure(""); setDeleteTarget(provider); }}>删除</button>}
            </span>
          </div>
          <ul className="models-list" aria-label={`${provider.name || provider.id} 的模型`}>
            {provider.models.map(model => <li key={model}><span>{model}</span><small>{effortSummary(provider, model)}</small></li>)}
            {!provider.models.length && <li className="models-hint">尚未添加模型</li>}
          </ul>
          {check && <p className={check.ok ? "models-hint" : "models-error"} role="status">{check.ok
            ? `已读取能力 · ${checkedAt(check.at) ?? "刚刚"}`
            : `读取能力失败：${check.message || "服务没有返回模型信息"}${checkedAt(check.at) ? `；仍显示 ${checkedAt(check.at)} 的结果` : ""}`}</p>}
          {open && <ProviderEditor key={provider.id} editing={provider} taken={taken} onBusyChange={setBusy}
            onCancel={() => setEditing(null)} onSaved={value => savedAs(value, provider)} />}
        </li>;
      })}
    </ul>
    <div className="models-add">
      {addOpen ? <Tabs.Root className="models-add-card" value={addMode} onValueChange={value => setAddMode(value as AddMode)}>
        <div className="models-add-modes">
          <Tabs.List className="models-segmented" aria-label="添加方式">
            <Tabs.Trigger value="catalog" disabled={busy || !catalogLeft.length} title={catalogLeft.length ? undefined : "目录中的提供商都已添加"}>第三方模型提供商</Tabs.Trigger>
            <Tabs.Trigger value="custom" disabled={busy}>自定义模型 API</Tabs.Trigger>
          </Tabs.List>
          <p className="models-hint">{addMode === "catalog" ? "从内置目录中选择 DeepSeek、OpenAI 等提供商，填入其 API 密钥即可使用。"
            : "连接中转站、自部署服务或其他兼容 OpenAI 协议的接口，需填写 API 地址和模型。"}</p>
        </div>
        {catalogLeft.length > 0 && <Tabs.Content value="catalog" className="models-add-panel">
          <CatalogPanel choices={catalogLeft} taken={taken} onBusyChange={setBusy} onCancel={() => setAddOpen(false)}
            onSaved={(value, provider) => savedAs(value, provider)} />
        </Tabs.Content>}
        <Tabs.Content value="custom" className="models-add-panel">
          <ProviderEditor key="custom" custom taken={taken} onBusyChange={setBusy} onCancel={() => setAddOpen(false)}
            onSaved={(value, provider) => savedAs(value, provider)} />
        </Tabs.Content>
      </Tabs.Root> : <button type="button" className="models-add-button" disabled={busy || !directory}
        onClick={() => { setSaved(null); setEditing(null); setAddMode(catalogLeft.length ? "catalog" : "custom"); setAddOpen(true); }}>
        <Plus size={14} aria-hidden="true" />添加模型提供商</button>}
    </div>
    <AlertDialog.Root open={!!deleteTarget} onOpenChange={open => { if (!open && !busy) setDeleteTarget(null); }}>
      <AlertDialog.Portal container={root.current}>
        <AlertDialog.Overlay className="models-overlay" />
        <AlertDialog.Content className="models-delete">
          {deleteTarget && <>
            <AlertDialog.Title>删除 {label(deleteTarget)}？</AlertDialog.Title>
            <AlertDialog.Description>删除 {label(deleteTarget)} 会移除其配置和密钥。正在使用它的对话需要重新选择模型；正在执行和排队中的任务保留原配置。</AlertDialog.Description>
            {deleteFailure && <p className="models-error" role="alert">{deleteFailure}</p>}
            <div className="models-editor-actions">
              <AlertDialog.Cancel asChild><button type="button" className="models-secondary" disabled={busy}>取消</button></AlertDialog.Cancel>
              <button type="button" className="models-secondary models-delete-confirm" disabled={busy} onClick={() => void confirmDelete()}>
                {busy ? "正在删除…" : `删除 ${label(deleteTarget)}`}</button>
            </div>
          </>}
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  </div>;
}

/** Declared effort of one model, in the provider's own terms; unknown is never shown as supported. */
function effortSummary(provider: ModelProvider, model: string) {
  const capability = provider.capabilities?.[model];
  if (!capability || capability.status === "unknown") return "Effort unconfirmed";
  if (capability.status === "unsupported") return "No effort control";
  const names = capability.supported_levels.map(level => EFFORT_NAMES[level]).join(" · ");
  return capability.default_level ? `${names} (default ${EFFORT_NAMES[capability.default_level]})` : `${names} (no declared default)`;
}
const checkedAt = (at: string | null) => at ? new Date(at).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : null;

/** The catalogue mode: pick a known provider, then only its key and models remain. */
function CatalogPanel({ choices, taken, onBusyChange, onCancel, onSaved }: {
  choices: typeof CATALOG; taken: string[]; onBusyChange: Busy; onCancel: () => void; onSaved: (value: ModelDirectory, provider: { id: string; name: string }) => void;
}) {
  const [picked, setPicked] = useState(choices[0].id);
  const preset = choices.find(c => c.id === picked) ?? choices[0];
  return <>
    <label className="models-field"><span className="models-label">提供商</span>
      <select className="models-input models-select" value={preset.id} aria-label="提供商" onChange={e => setPicked(e.target.value)}>
        {choices.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select></label>
    <ProviderEditor key={preset.id} preset={preset} taken={taken} onBusyChange={onBusyChange} onCancel={onCancel} onSaved={onSaved} />
  </>;
}

/**
 * One editor card: an existing provider, a catalogue preset or a custom API. Saving a key is not the same as a working
 * connection, so the connection test is its own action; the key field left blank keeps the stored key at an unchanged address.
 */
function ProviderEditor({ editing, preset, custom = false, taken, onBusyChange, onCancel, onSaved }: {
  editing?: ModelProvider; preset?: (typeof CATALOG)[number]; custom?: boolean; taken: string[];
  onBusyChange: Busy; onCancel: () => void; onSaved: (value: ModelDirectory, provider: { id: string; name: string }) => void;
}) {
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const [draft, setDraft] = useState<ProviderInput>(() => editing
    ? { id: editing.id, name: editing.name, base_url: editing.base_url, api_key: "", models: [...editing.models], action_protocol: editing.action_protocol }
    : { id: preset?.id ?? "", name: preset?.name ?? "", base_url: preset?.base_url ?? "", api_key: "", models: [], action_protocol: preset?.action_protocol ?? "json" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  const [catalog, setCatalog] = useState<string[] | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  useEffect(() => { onBusyChange(busy); }, [busy, onBusyChange]);
  // A save closes this card while it is still busy; leaving must release the section, or the window stays locked.
  const report = useRef(onBusyChange);
  report.current = onBusyChange;
  useEffect(() => () => report.current(false), []);
  const change = (patch: Partial<ProviderInput>) => { setDraft(value => ({ ...value, ...patch })); setMessage(null); };
  const canKeepKey = !!editing?.has_api_key && normalizeUrl(draft.base_url) === normalizeUrl(editing.base_url);
  const keyError = apiKeyFailure(draft.api_key);
  const modelError = !draft.models.length || draft.models.some(m => !m.trim()) || new Set(draft.models.map(m => m.trim())).size !== draft.models.length;
  const routeError = !ROUTE.test(draft.id) || (!editing && taken.includes(draft.id));
  const ready = !!draft.base_url.trim() && !routeError && !keyError && (!!draft.api_key || canKeepKey);
  const run = async (work: () => Promise<void>) => {
    setBusy(true); setMessage(null);
    try { await work(); }
    catch (failure) { if (alive.current) setMessage({ text: failure instanceof Error ? failure.message : "操作失败，请重试。", error: true }); }
    finally { if (alive.current) setBusy(false); }
  };
  const value = () => ({ ...draft, name: draft.name.trim(), base_url: normalizeUrl(draft.base_url), models: draft.models.map(m => m.trim()) });
  const showsAddress = custom || !!editing;
  const visible = catalog?.filter(m => m.toLowerCase().includes(query.toLowerCase())) ?? [];
  return <div className="models-editor">
    {editing && <div className="models-editor-head"><span className="models-editor-title">编辑 {editing.name || editing.id}</span><span className="models-editor-route">{editing.id}</span></div>}
    {custom && <>
      <label className="models-field"><span className="models-label">提供商 ID</span>
        <input className="models-input" value={draft.id} placeholder="my-gateway" maxLength={64} disabled={busy} onChange={e => change({ id: e.target.value })} /></label>
      {draft.id && routeError ? <p className="models-error">ID 须以小写字母开头，仅含小写字母、数字或连字符，且不能重复。</p>
        : <p className="models-hint">用于区分提供商，保存后不能修改。</p>}
      <label className="models-field"><span className="models-label">显示名称</span>
        <input className="models-input" value={draft.name} placeholder={draft.id || "显示名称"} maxLength={100} disabled={busy} onChange={e => change({ name: e.target.value })} /></label>
    </>}
    {showsAddress && <label className="models-field"><span className="models-label">API 地址</span>
      <input className="models-input" type="url" value={draft.base_url} placeholder="https://api.example.com/v1" maxLength={2048} disabled={busy}
        onChange={e => { change({ base_url: e.target.value, api_key: "" }); setCatalog(null); }} /></label>}
    <label className="models-field"><span className="models-label">API 密钥</span>
      <input className="models-input" type="password" autoComplete="new-password" value={draft.api_key} maxLength={8192} disabled={busy}
        placeholder={canKeepKey ? "已保存；留空保留原密钥" : "输入 API 密钥"} onChange={e => change({ api_key: e.target.value })} />
      {keyError && <span className="models-error">请仅粘贴密钥本身，不要包含引号、空白或环境变量赋值。</span>}</label>
    <section className="models-catalog" aria-label="模型目录">
      <div className="models-catalog-head"><span className="models-label">模型目录</span>
        <button type="button" className="models-small" disabled={busy || !ready} onClick={() => void run(async () => {
          const result = await api.providerCatalog({ ...value(), models: [] });
          if (!alive.current) return;
          if (!result.ok) { setMessage({ text: result.message, error: true }); return; }
          setCatalog(result.models); setPicked(new Set(draft.models)); setQuery("");
        })}>获取可用模型</button></div>
      {draft.models.map((model, index) => <div className="models-model-row" key={index}>
        <input className="models-input" aria-label={`模型 ID ${index + 1}`} value={model} placeholder="模型 ID" maxLength={200} disabled={busy}
          onChange={e => change({ models: draft.models.map((m, i) => i === index ? e.target.value : m) })} />
        <button type="button" className="models-icon" aria-label={`移除模型 ${index + 1}`} disabled={busy}
          onClick={() => change({ models: draft.models.filter((_, i) => i !== index) })}><X size={14} /></button>
      </div>)}
      {!draft.models.length && <p className="models-empty">还没有模型。获取可用模型，或手动添加。</p>}
      <button type="button" className="models-small" disabled={busy || draft.models.length >= 100} onClick={() => change({ models: [...draft.models, ""] })}>
        <Plus size={13} aria-hidden="true" />添加模型</button>
      {catalog !== null && <div className="models-candidates">
        <input className="models-input" aria-label="搜索模型" placeholder="搜索模型" value={query} onChange={e => setQuery(e.target.value)} />
        <ul>{visible.map(model => <li key={model}><label>
          <Checkbox.Root className="models-check" checked={picked.has(model)} aria-label={model}
            onCheckedChange={() => setPicked(current => { const next = new Set(current); if (next.has(model)) next.delete(model); else next.add(model); return next; })}>
            <Checkbox.Indicator><Check size={12} /></Checkbox.Indicator></Checkbox.Root>
          <span>{model}</span></label></li>)}</ul>
        {!visible.length && <p className="models-empty">没有可用模型，可手动添加。</p>}
        <div className="models-editor-actions">
          <button type="button" className="models-secondary" onClick={() => setCatalog(null)}>取消</button>
          <button type="button" className="models-primary" disabled={!picked.size || picked.size > 100}
            onClick={() => { change({ models: [...new Set([...draft.models.filter(m => m.trim()), ...picked])] }); setCatalog(null); }}>添加所选模型</button>
        </div>
      </div>}
    </section>
    {(custom || editing) && <Collapsible.Root className="models-advanced">
      <Collapsible.Trigger className="models-advanced-trigger"><ChevronRight size={12} aria-hidden="true" />高级设置</Collapsible.Trigger>
      <Collapsible.Content className="models-advanced-body">
        <label className="models-field"><span className="models-label">工具调用方式</span>
          <select className="models-input models-select" value={draft.action_protocol} disabled={busy} onChange={e => change({ action_protocol: e.target.value })}>
            <option value="json">通用</option><option value="deepseek_tools">DeepSeek 工具调用</option></select></label>
        <p className="models-hint">密钥只保存在服务器私有目录；更换 API 地址需重新填写密钥。</p>
      </Collapsible.Content>
    </Collapsible.Root>}
    {message && <p className={message.error ? "models-error" : "models-saved"} role={message.error ? "alert" : "status"}>{message.text}</p>}
    <div className="models-editor-actions">
      <button type="button" className="models-link" disabled={busy || !ready || modelError} title="发送固定文本，可能产生少量调用费用"
        onClick={() => void run(async () => {
          const result = await api.testProvider(value());
          if (alive.current) setMessage({ text: result.message, error: !result.ok });
        })}>测试连接</button>
      <span className="models-editor-spacer" />
      <button type="button" className="models-secondary" disabled={busy} onClick={onCancel}>取消</button>
      <button type="button" className="models-primary" disabled={busy || !ready || modelError}
        onClick={() => void run(async () => { const result = await api.saveProvider(value()); if (alive.current) onSaved(result, { id: draft.id, name: draft.name.trim() }); })}>
        {busy ? "正在保存…" : editing ? "保存更改" : "创建提供商"}</button>
    </div>
    {modelError && draft.models.length > 0 && <p className="models-hint">模型 ID 不能为空或重复。</p>}
  </div>;
}
