import { useEffect, useMemo, useRef, useState } from "react";
import { readBoundedText } from "./ResultsPane";
import {sameKey} from './spatial/types';
import { object } from "./graphData";

type Point = {record_id: string; x: number; y: number; group: string};
type Plot = {missing_genes?: string[]; records: Point[]; n_observations: number; colors: Record<string, (string | number | null)[]>;
  composition: {group: string; count: number; fraction: number}[]};
const finite = (x: unknown): x is number => typeof x === "number" && Number.isFinite(x);
export function parseUMAP(value: unknown): Plot | null {
  if (!object(value) || value.schema_ref !== "bridge://schemas/expression-plot-data/v0.1" || value.kind !== "umap"
    || !Number.isSafeInteger(value.n_observations) || Number(value.n_observations) <= 0
    || !Array.isArray(value.records) || !value.records.length || value.records.length > 20000
    || value.records.length > Number(value.n_observations) || !object(value.colors) || !Array.isArray(value.composition)) return null;
  if (value.missing_genes !== undefined && (!Array.isArray(value.missing_genes) || !value.missing_genes.every(g => typeof g === "string"))) return null;
  const n = value.records.length;
  if (!value.records.every(p => object(p) && typeof p.record_id === "string" && finite(p.x) && finite(p.y) && typeof p.group === "string")
    || new Set(value.records.map(p => p.record_id)).size !== value.records.length
    || !Object.values(value.colors).every(c => Array.isArray(c) && c.length === n
      && c.every(v => v === null || typeof v === "string" || finite(v)))
    || !value.composition.every(g => object(g) && typeof g.group === "string" && Number.isSafeInteger(g.count)
      && Number(g.count) >= 0 && finite(g.fraction) && Math.abs(g.fraction - Number(g.count) / Number(value.n_observations)) < 1e-10)
    || value.composition.reduce((n, g) => n + Number(g.count), 0) !== value.n_observations) return null;
  return value as Plot;
}
const palette = ["#2563eb", "#dc2626", "#059669", "#9333ea", "#d97706", "#0891b2", "#db2777", "#475569"];
function Scatter({data}: {data: Plot}) {
  const [color, setColor] = useState("分群");
  const [group, setGroup] = useState("");
  const [hover, setHover] = useState("");
  const canvas = useRef<HTMLCanvasElement>(null);
  const values = data.colors[color] ?? data.colors[Object.keys(data.colors)[0]] ?? [];
  const continuous = values.some(v => typeof v === "number") && values.every(v => v === null || typeof v === "number");
  const categories = [...new Set(values.filter((v): v is string => typeof v === "string"))].sort();
  const range = values.filter(finite);
  const low = range.length ? Math.min(...range) : 0, high = range.length ? Math.max(...range) : 1;
  const pointColor = (i: number) => values[i] === null ? "#94a3b8" : continuous
    ? "hsl(" + (240 - 220 * (Number(values[i]) - low) / (high - low || 1)) + " 70% 45%)"
    : palette[categories.indexOf(String(values[i])) % palette.length] ?? "#94a3b8";
  const positions = useMemo(() => {
    const xs = data.records.map(p => p.x), ys = data.records.map(p => p.y);
    const left = Math.min(...xs), right = Math.max(...xs), bottom = Math.min(...ys), top = Math.max(...ys);
    const scale = Math.min(680 / (right - left || 1), 380 / (top - bottom || 1));
    return data.records.map(p => ({x: 380 + (p.x - (left + right) / 2) * scale,
      y: 220 - (p.y - (bottom + top) / 2) * scale}));
  }, [data]);
  useEffect(() => {
    const ctx = canvas.current?.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, 760, 440);
    data.records.forEach((p, i) => {
      if (group && p.group !== group) return;
      ctx.fillStyle = pointColor(i); ctx.globalAlpha = 0.75;
      ctx.beginPath(); ctx.arc(positions[i].x, positions[i].y, 2.2, 0, Math.PI * 2); ctx.fill();
    });
    ctx.globalAlpha = 1;
  }, [data, color, group, positions]);
  const shown = data.records.filter(p => !group || p.group === group).length;
  const total = group ? data.composition.find(g => g.group === group)?.count : data.n_observations;
  return <section aria-label="交互式 UMAP">
    <label>着色 <select value={color} onChange={e => setColor(e.target.value)}>
      {Object.keys(data.colors).map(key => <option key={key}>{key}</option>)}</select></label>
    <label>查看分群 <select value={group} onChange={e => setGroup(e.target.value)}><option value="">全部分群</option>
      {data.composition.map(g => <option key={g.group}>{g.group}</option>)}</select></label>
    {data.missing_genes?.length ? <p>所选数据未包含这些基因：{data.missing_genes.join("、")}；未补零。</p> : null}
    <p>当前显示 {shown} 个点；所选范围共 {total} 个细胞，完整数据共 {data.n_observations} 个细胞。显示抽样不改变统计。</p>
    <canvas ref={canvas} width={760} height={440} style={{width: "100%", maxWidth: 760, background: "#fff"}}
      role="img" aria-label="UMAP 表达相似性分布，坐标值可在下方同源数据表查看"
      onMouseLeave={() => setHover("")} onMouseMove={event => {
        const box = event.currentTarget.getBoundingClientRect();
        const x = (event.clientX - box.left) * 760 / box.width, y = (event.clientY - box.top) * 440 / box.height;
        let near = -1, distance = 64;
        positions.forEach((p, i) => { if (group && data.records[i].group !== group) return;
          const d = (x - p.x) ** 2 + (y - p.y) ** 2; if (d < distance) {distance = d; near = i;} });
        setHover(near < 0 ? "" : data.records[near].group + " · " + color + ": " + (values[near] ?? "缺失"));
      }} />
    <p aria-live="polite">{hover || "悬停查看分群和着色值；键盘可使用上方选择框及下方数据表。"}</p>
    {continuous ? <p>色标：蓝 {low.toPrecision(4)} → 红 {high.toPrecision(4)}；灰色为缺失。</p>
      : <div aria-label="颜色图例">{categories.map((name, i) => <span key={name} style={{display: "inline-block", marginRight: 16}}>
        <span aria-hidden="true" style={{color: palette[i % palette.length]}}>● </span>{name}</span>)}</div>}
    <details><summary>完整分群计数</summary><table><thead><tr><th>分群</th><th>细胞数</th><th>占完整数据</th></tr></thead>
      <tbody>{data.composition.map(g => <tr key={g.group}><td>{g.group}</td><td>{g.count}</td><td>{(100 * g.fraction).toFixed(2)}%</td></tr>)}</tbody></table></details>
  </section>;
}
export default function ExpressionUMAP({url}: {url: string}) {
  const [state, setState] = useState<{url: string; data: Plot | null} | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      let data = null;
      try { const response = await fetch(url + "/preview", {credentials: "same-origin", signal: controller.signal});
        if (response.ok) { const body = await readBoundedText(response, 24_000_000);
          if (!body.truncated) data = parseUMAP(JSON.parse(body.text)); }
      } catch { /* Static bound figure remains available. */ }
      if (!controller.signal.aborted) setState({url, data});
    })();
    return () => controller.abort();
  }, [url]);
  return state?.url === url && state.data ? <Scatter key={url} data={state.data} />
    : <p role="status">{state?.url === url ? "交互数据暂不可用，可查看下方静态图和完整表格。" : "正在加载交互数据…"}</p>;
}

/** Controlled display only: assignments and coordinates have already been joined by the server. */
export function ProductScatter({data,activeKey,mode,palette,onHover,onPin}:{
  data:import('./spatial/types').Product;activeKey:import('./spatial/types').SelectionKey|null;mode:'type'|'subtype'|'cluster';
  palette:Record<string,string>;onHover:(key:import('./spatial/types').SelectionKey|null)=>void;
  onPin:(key:import('./spatial/types').SelectionKey)=>void;
}) {
  const canvas=useRef<HTMLCanvasElement>(null);
  const hoverTimer=useRef<ReturnType<typeof setTimeout>|null>(null);
  const pendingHover=useRef<import('./spatial/types').SelectionKey|null|undefined>(undefined);
  function cancelHover(){
    if(hoverTimer.current!==null)clearTimeout(hoverTimer.current);
    hoverTimer.current=null;pendingHover.current=undefined;
  }
  useEffect(()=>cancelHover,[data,mode,onHover,activeKey]);
  function preview(key:import('./spatial/types').SelectionKey|null){
    // A stable group must persist briefly; tiny moves at mixed boundaries do not flash.
    if(pendingHover.current!==undefined&&sameKey(pendingHover.current,key))return;
    cancelHover();pendingHover.current=key;
    hoverTimer.current=setTimeout(()=>{hoverTimer.current=null;onHover(key);},120);
  }
  const positions=useMemo(()=>{
    const xs=data.records.map(p=>p.x),ys=data.records.map(p=>p.y);
    const l=Math.min(...xs),r=Math.max(...xs),b=Math.min(...ys),t=Math.max(...ys);
    const scale=Math.min(680/(r-l||1),420/(t-b||1));
    return data.records.map(p=>({x:380+(p.x-(l+r)/2)*scale,y:250-(p.y-(b+t)/2)*scale}));
  },[data]);
  const keyAt=(i:number)=>({kind:mode,id:mode==='cluster'?data.records[i].cluster:(mode==='subtype'?data.records[i].reference_subtype_id:data.records[i].type_id)??(data.records[i].assignment_state==='unavailable'?'__unavailable__':'__unknown__')});
  useEffect(()=>{const ctx=canvas.current?.getContext('2d');if(!ctx)return;
    ctx.clearRect(0,0,760,500);
    data.records.forEach((p,i)=>{const id=mode==='cluster'?p.cluster:(mode==='subtype'?p.reference_subtype_id:p.type_id)??(p.assignment_state==='unavailable'?'__unavailable__':'__unknown__');
      const selected=!activeKey||activeKey.kind===mode&&activeKey.id===id;
      ctx.fillStyle=selected?palette[id]??'#87948d':'#dbe0dd';ctx.globalAlpha=selected?.85:.45;
      ctx.beginPath();ctx.arc(positions[i].x,positions[i].y,selected?2.5:1.7,0,Math.PI*2);ctx.fill();});ctx.globalAlpha=1;
  },[data,activeKey,mode,palette,positions]);
  function nearest(event:React.MouseEvent<HTMLCanvasElement>){const box=event.currentTarget.getBoundingClientRect();
    const x=(event.clientX-box.left)*760/box.width,y=(event.clientY-box.top)*500/box.height;
    let found=-1,distance=80;positions.forEach((p,i)=>{const d=(p.x-x)**2+(p.y-y)**2;if(d<distance){distance=d;found=i;}});return found;}
  return <div className="product-scatter-frame"><canvas ref={canvas} width={760} height={500} className="product-scatter" role="img"
    aria-label="产品 UMAP；可悬停预览或点击锁定，图旁类别按钮支持键盘操作"
    onMouseLeave={()=>{cancelHover();onHover(null);}} onMouseMove={e=>{const i=nearest(e);preview(i<0?null:keyAt(i));}}
    onClick={e=>{cancelHover();const i=nearest(e);if(i>=0)onPin(keyAt(i));}}/>
    <svg viewBox="0 0 760 500" className="product-scatter-axes" aria-hidden="true"><path d="M35 427V473H99" fill="none" stroke="#48535c" strokeWidth="1"/>
      <text x="105" y="478" fontSize="13" fill="#26343e">UMAP 1</text><text transform="translate(28 420) rotate(-90)" fontSize="13" fill="#26343e">UMAP 2</text></svg></div>;
}
