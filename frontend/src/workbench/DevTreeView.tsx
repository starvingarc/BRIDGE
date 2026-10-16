import { useEffect, useMemo, useRef, useState } from "react";
import { ChainRings } from "./ChainRings";
import { MappingLens, MarkerKey } from "./MappingLens";
import { expressionCeiling, markerMismatch } from "./mapping";
import { readPalette, seeded } from "./palette";
import { isLow, targetFraction } from "./stages";
import { bandWidth, MIN_SHARE, onThisTree, segmentDistance, shownIndex } from "./treeFlow";
import { buildAtlas, drawTree, familyOf, ORIGIN, project, toWorld, type Camera, type DrawState, type Expression, type Flight, type Vec3 } from "./treeScene";
import type { DevTree, MarkerPanel, Protocol, Sample } from "./types";
import { prefersMotion, useFrame } from "./useFrame";

type Props = {
  tree: DevTree; protocols: Protocol[]; focus: Protocol | null;
  onFocus: (id: string | null) => void; onOpenProtocol: (id: string) => void; onAsk: (question: "why" | "next", protocol: Protocol, sample: number) => void;
  /** Opens this sample day of the focused run, e.g. after it was picked in the run bar; a day without a result closes the open one. */
  openDay?: { key: number; day: number; sampleId?: string } | null;
  /** Reports a sample opened on the tree itself, from a flow band or the lens. */
  onSample?: (protocolId: string, sample: Sample) => void;
  /** A small preview inside the sample panel: the tree and the day's cells only, without the lens and controls. */
  compact?: boolean;
  /** Reads a mapping result's stored marker expression; absent for examples. */
  loadMarkers?: (assessmentId: string, signal: AbortSignal) => Promise<MarkerPanel>;
};

type Markers = { id: string; panel?: MarkerPanel; error?: string };

const HOME = { x: -130, y: 0, z: 0, scale: 1 };

/** Camera goal that fits a set of world points: centred on their extent, zoomed in only as far as they all stay in view. */
function frame(points: Vec3[]) {
  const lo = [0, 1, 2].map(i => Math.min(...points.map(p => p[i]))), hi = [0, 1, 2].map(i => Math.max(...points.map(p => p[i])));
  const spanX = Math.max(hi[0] - lo[0], hi[2] - lo[2], 1), spanY = Math.max(hi[1] - lo[1], 1);
  const scale = Math.max(0.9, Math.min(2.1, 0.75 * Math.min(1390 / spanX, 890 / spanY)));
  return { x: (lo[0] + hi[0]) / 2, y: (lo[1] + hi[1]) / 2, z: (lo[2] + hi[2]) / 2, scale };
}


export function DevTreeView({ tree, protocols, focus, onFocus, onOpenProtocol, onAsk, openDay, onSample, compact, loadMarkers }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const pin = useRef<HTMLDivElement>(null);
  const atlas = useMemo(() => buildAtlas(tree), [tree]);
  const motion = prefersMotion();
  const [sampleIndex, setSampleIndex] = useState<number | null>(null);
  const [colorBy, setColorBy] = useState<"lineage" | "week" | "gene">("lineage");
  const [gene, setGene] = useState<string | null>(null);
  const [markers, setMarkers] = useState<Markers | null>(null);
  const [maxWeek, setMaxWeek] = useState(25);
  const [playing, setPlaying] = useState(false);
  const cam = useRef<Camera>({ yaw: -0.5, pitch: 0.28, ...HOME });
  const goal = useRef({ ...HOME });
  const yawBase = useRef(-0.5);
  const lastDrag = useRef(0);
  const drag = useRef<{ x: number; y: number; moved: number } | null>(null);
  const hoverNode = useRef<number | null>(null);
  const flows = useRef(new Map<string, Map<string, number>>());
  const hoverRun = useRef<string | null>(null);
  const runTip = useRef<HTMLDivElement>(null);
  const flights = useRef<Flight[]>([]);
  const flightStart = useRef(0);
  const growStart = useRef(performance.now());
  const week = useRef(25);

  const pending = useRef<number | null>(null);
  /** The run and day whose cells are flying or landed, so a repeated pick of the same day does not restart them. */
  const shown = useRef<string | null>(null);
  useEffect(() => {
    if (pending.current !== null) { setSampleIndex(pending.current); pending.current = null; }
    else { shown.current = null; setSampleIndex(null); goal.current = { ...HOME }; }
  }, [focus?.id]);

  const enter = (protocol: Protocol, index: number) => {
    const sample = protocol.samples[index];
    shown.current = `${protocol.id}:${index}`;
    // Cells set off from hPSC and land where the mapping placed them.
    const from: Vec3 = ORIGIN;
    const floorShare = sample.chain[3] ?? 0.5;
    const limit = index === 0 ? 0.2 : index === 1 ? 0.45 : 1;
    const pool = (names: string[]) => atlas.points.filter(p => names.includes(tree.subtypes[p.node]) && p.pt <= limit);
    const late = sample.day > 20;
    const good = pool(late ? ["Nb_mFP", "Neuron_DA"] : ["RG_mFP", "Nb_mFP"]);
    const off = pool(late ? ["Nb_mBIP", "Neuron_Glut", "Neuron_GABA"] : ["RG_mBIP", "Nb_mBIP"]);
    const side = pool(["RG_mBMP", "Nb_mBMP"]);
    const random = seeded(index * 97 + protocol.id.charCodeAt(0));
    const cells = onThisTree(sample, tree) ? sample.mappedCells ?? [] : [];
    // Cells copy the position of their nearest reference cell, so many share one point; a shared point grows with its count.
    const stacks = new Map<string, { cell: [number, number, number, number]; rows: number[] }>();
    cells.forEach((cell, row) => { const key = cell.join(); const stack = stacks.get(key); if (stack) stack.rows.push(row); else stacks.set(key, { cell, rows: [row] }); });
    const next: Flight[] = [...stacks.values()].map(({ cell: [x, y, z, node], rows }) => ({
      from, to: toWorld([x, y, z]), family: familyOf(tree.subtypes[node] ?? ""), delay: random() * 900, rows,
      r: Math.min(7, 2.4 + 1.1 * Math.sqrt(rows.length - 1)) + random() * 0.4,
    }));
    for (let k = 0; !sample.mappedCells && k < 520; k += 1) {
      const source = random() < 0.1 && side.length ? side : random() < floorShare ? good : off;
      const target = source[Math.floor(random() * source.length)];
      if (target) next.push({ from, to: target.p, family: familyOf(tree.subtypes[target.node]), delay: random() * 900, r: 2.4 + random() * 0.6 });
    }
    onSample?.(protocol.id, sample);
    flights.current = next; flightStart.current = performance.now();
    goal.current = next.length ? frame(next.map(f => f.to)) : { ...HOME };
    if (focus?.id !== protocol.id) { pending.current = index; onFocus(protocol.id); }
    else setSampleIndex(index);
  };
  const leave = () => { shown.current = null; setSampleIndex(null); goal.current = { ...HOME }; };

  // Marker expression is read only while colouring by gene, for the open result; a stale response is dropped.
  const open = focus && sampleIndex !== null ? focus.samples[sampleIndex] : null;
  const markerSource = open?.mapping?.markers ?? null;
  const geneMode = colorBy === "gene" && !!markerSource && !!loadMarkers;
  useEffect(() => { if (colorBy === "gene" && !markerSource) setColorBy("lineage"); }, [colorBy, markerSource]);
  useEffect(() => {
    if (!geneMode || !markerSource || markers?.id === markerSource.assessmentId) return;
    const controller = new AbortController(), id = markerSource.assessmentId;
    setMarkers({ id });
    loadMarkers!(id, controller.signal)
      .then(panel => { if (!controller.signal.aborted) setMarkers({ id, panel }); })
      .catch(failure => { if (!controller.signal.aborted) setMarkers({ id, error: failure instanceof Error ? failure.message : "表达数据读取失败。" }); });
    return () => controller.abort();
  }, [geneMode, markerSource?.assessmentId]);
  const current = geneMode && markers?.id === markerSource?.assessmentId ? markers : null;
  const panel = current?.panel ?? null;
  const mismatch = panel && open?.mapping ? markerMismatch(panel, open.mapping, tree.synthetic ? undefined : tree.version) : null;
  const shownGene = panel ? (panel.genes.find(g => g.gene === gene && g.available) ?? panel.genes.find(g => g.available))?.gene ?? null : null;
  const expression = useMemo<Expression | null>(() => {
    if (!panel || mismatch || !shownGene) return null;
    const column = panel.genes.findIndex(g => g.gene === shownGene);
    const sample = panel.sample[column] ?? [];
    const reference = panel.reference;
    const ceiling = expressionCeiling([...sample, ...[...reference.values()].map(row => row[column] ?? null)]);
    return { column, reference, sample, ceiling };
  }, [panel, mismatch, shownGene]);
  // Declared after the focus effect so a day picked together with a new focus is not reset by it.
  const opened = useRef<number | null>(null);
  useEffect(() => {
    if (!openDay || !focus || opened.current === openDay.key) return;
    opened.current = openDay.key;
    const index = openDay.sampleId ? focus.samples.findIndex(s => s.sampleId === openDay.sampleId) : focus.samples.findIndex(s => s.day === openDay.day);
    if (index < 0) leave();
    else if (shown.current !== `${focus.id}:${index}`) enter(focus, index);
  });

  useFrame(now => {
    const el = canvas.current; if (!el) return;
    const ctx = el.getContext("2d"); if (!ctx) return;
    const rect = el.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (el.width !== Math.round(rect.width * dpr)) { el.width = Math.round(rect.width * dpr); el.height = Math.round(rect.height * dpr); }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const c = cam.current, g = goal.current, k = motion ? 0.06 : 1;
    c.x += (g.x - c.x) * k; c.y += (g.y - c.y) * k; c.z += (g.z - c.z) * k; c.scale += (g.scale - c.scale) * k;
    if (!drag.current && motion && now - lastDrag.current > 2500) c.yaw += (yawBase.current + Math.sin(now / 8300) * 0.4 - c.yaw) * 0.01;
    if (playing) { week.current = Math.min(25, week.current + 0.05); if (Math.round(week.current) !== maxWeek) setMaxWeek(Math.round(week.current)); if (week.current >= 25) setPlaying(false); }
    const state: DrawState = { tree, atlas, protocols, focus, sampleIndex, flights: flights.current, flightStart: flightStart.current, growStart: growStart.current, maxWeek: playing ? week.current : maxWeek,
      colorBy: geneMode ? "gene" : colorBy === "gene" ? "lineage" : colorBy, hoverNode: hoverNode.current, expression,
      flows: flows.current, hoverRun: hoverRun.current };
    drawTree(ctx, rect.width, rect.height, c, state, readPalette(el), now, motion);
    if (pin.current && focus && sampleIndex !== null) {
      const current = focus.samples[sampleIndex];
      // A real result points at the branch most of its cells reached; examples point by their floor-plate level.
      const top = current.mapping?.branches[0]?.label;
      const name = current.mapping ? top : isLow(current.chain[3]) ? "Nb_mBIP" : "Nb_mFP";
      const anchor = (name !== undefined ? atlas.nodes[tree.subtypes.indexOf(name)] : undefined) ?? atlas.nodes[0];
      const [x, y] = project(c, rect.width, rect.height, anchor);
      pin.current.style.left = `${x}px`; pin.current.style.top = `${y}px`;
    }
  });

  /** The run whose drawn flow is under the pointer; where flows overlap, the one carrying the larger share there. */
  const hit = (clientX: number, clientY: number) => {
    const el = canvas.current; if (!el) return null;
    const rect = el.getBoundingClientRect(), x = clientX - rect.left, y = clientY - rect.top;
    let best: { protocol: Protocol; index: number; share: number } | null = null;
    for (const p of focus ? [focus] : protocols) {
      if (!p.samples.length) continue;
      for (const [key, share] of flows.current.get(p.id) ?? []) {
        if (share < MIN_SHARE || (best && best.share >= share)) continue;
        const [from, to] = key.split(">").map(Number);
        const a = project(cam.current, rect.width, rect.height, from < 0 ? ORIGIN : atlas.nodes[from]), b = project(cam.current, rect.width, rect.height, atlas.nodes[to]);
        if (segmentDistance(x, y, a[0], a[1], b[0], b[1]) <= Math.max(8, bandWidth(share, cam.current.scale) / 2 + 3))
          best = { protocol: p, index: shownIndex(p, focus, sampleIndex), share };
      }
    }
    return best;
  };

  const sample = focus && sampleIndex !== null ? focus.samples[sampleIndex] : null;
  const fraction = sample ? targetFraction(sample.chain) : null;
  if (compact) return <section className="wb-tree wb-tree--compact" aria-label="发育树预览">
    <canvas ref={canvas} className="wb-tree-canvas" aria-label="这个样本的细胞在发育树上的位置；拖动旋转。"
      onPointerDown={e => { drag.current = { x: e.clientX, y: e.clientY, moved: 0 }; e.currentTarget.setPointerCapture?.(e.pointerId); }}
      onPointerMove={e => {
        if (!drag.current) return;
        const dx = e.clientX - drag.current.x, dy = e.clientY - drag.current.y;
        drag.current = { x: e.clientX, y: e.clientY, moved: drag.current.moved + Math.abs(dx) + Math.abs(dy) };
        cam.current.yaw += dx * 0.006; yawBase.current += dx * 0.006;
        cam.current.pitch = Math.max(-1.1, Math.min(1.1, cam.current.pitch + dy * 0.005)); lastDrag.current = performance.now();
      }}
      onPointerUp={() => { drag.current = null; }} />
  </section>;
  return <section className="wb-tree" aria-label="发育树">
    <canvas ref={canvas} className="wb-tree-canvas" aria-label="三维发育树。每次实验显示为沿树枝分叉的流带，粗细是细胞占比；拖动旋转，点击流带查看细胞落在哪根枝上。"
      onPointerDown={e => { drag.current = { x: e.clientX, y: e.clientY, moved: 0 }; e.currentTarget.setPointerCapture?.(e.pointerId); }}
      onPointerMove={e => {
        if (drag.current) {
          const dx = e.clientX - drag.current.x, dy = e.clientY - drag.current.y;
          drag.current = { x: e.clientX, y: e.clientY, moved: drag.current.moved + Math.abs(dx) + Math.abs(dy) };
          cam.current.yaw += dx * 0.006; yawBase.current += dx * 0.006;
          cam.current.pitch = Math.max(-1.1, Math.min(1.1, cam.current.pitch + dy * 0.005)); lastDrag.current = performance.now();
          return;
        }
        const rect = e.currentTarget.getBoundingClientRect(); hoverNode.current = null;
        atlas.nodes.forEach((n, i) => { const [x, y] = project(cam.current, rect.width, rect.height, n); if (Math.hypot(x - (e.clientX - rect.left), y - (e.clientY - rect.top)) < 14) hoverNode.current = i; });
        const over = hit(e.clientX, e.clientY);
        e.currentTarget.style.cursor = over ? "pointer" : "";
        hoverRun.current = over && !focus ? over.protocol.id : null;
        const tip = runTip.current;
        if (tip) {
          tip.hidden = !over || sampleIndex !== null;
          if (over) { tip.textContent = `${over.protocol.name} · D${over.protocol.samples[over.index].day}`; tip.style.left = `${e.clientX - rect.left + 14}px`; tip.style.top = `${e.clientY - rect.top + 14}px`; }
        }
      }}
      onPointerLeave={() => { hoverRun.current = null; if (runTip.current) runTip.current.hidden = true; }}
      onPointerUp={e => { const moved = (drag.current?.moved ?? 0) > 6; drag.current = null; if (moved) return; const found = hit(e.clientX, e.clientY); if (found) enter(found.protocol, found.index); }}
    />
    <div ref={runTip} className="wb-run-tip" role="tooltip" hidden />
    {sample && focus && sample.mapping && <MappingLens sample={sample} onTree={onThisTree(sample, tree)}>
      {geneMode && <MarkerKey panel={panel} gene={shownGene} onGene={setGene} ceiling={expression?.ceiling ?? null}
        status={!current || (!current.panel && !current.error) ? "loading" : current.error ?? mismatch ?? null} />}
      <span className="wb-days" role="group" aria-label="取样天数">
        {focus.samples.map((s, i) => <button key={s.sampleId ?? i} aria-pressed={i === sampleIndex} onClick={() => enter(focus, i)}>D{s.day}</button>)}
      </span>
      <span className="wb-lens-ask"><button onClick={() => onAsk("why", focus, sampleIndex!)}>为什么</button><button onClick={() => onAsk("next", focus, sampleIndex!)}>下一版</button></span>
      <button className="wb-link" onClick={() => onOpenProtocol(focus.id)}>查看方案图</button>
    </MappingLens>}
    {sample && focus && !sample.mapping && <aside className="wb-lens" aria-label="取样点摘要">
      <span className="wb-lens-day">D{sample.day} · {sample.gestation}</span>
      <span className="wb-lens-pct">{fraction === null ? "—" : <>{Math.round(fraction * 100)}<sup>%</sup></>}</span>
      <span className="wb-muted">是你要的细胞</span>
      <ChainRings values={sample.chain} />
      <span className="wb-days" role="group" aria-label="取样天数">
        {focus.samples.map((s, i) => <button key={s.sampleId ?? i} aria-pressed={i === sampleIndex} onClick={() => enter(focus, i)}>D{s.day}</button>)}
      </span>
      <button className="wb-link" onClick={() => onOpenProtocol(focus.id)}>查看方案图</button>
    </aside>}
    {sample && focus && <div className="wb-pin" ref={pin} role="note">
      <span>{sample.note}</span>
      <span className="wb-pin-actions"><button onClick={() => onAsk("why", focus, sampleIndex!)}>为什么</button><button onClick={() => onAsk("next", focus, sampleIndex!)}>下一版</button></span>
    </div>}
    <div className="wb-tree-controls">
      <span className="wb-seg" role="group" aria-label="着色">
        <button aria-pressed={colorBy === "lineage"} onClick={() => setColorBy("lineage")}>谱系</button>
        <button aria-pressed={colorBy === "week"} onClick={() => setColorBy("week")}>孕周</button>
        {markerSource && loadMarkers && <button aria-pressed={colorBy === "gene"} onClick={() => setColorBy("gene")}>基因</button>}
      </span>
      <button className="wb-play" aria-label={playing ? "暂停孕周回放" : "回放孕周"} onClick={() => { if (!playing && maxWeek >= 25) week.current = 7; setPlaying(!playing); }}>{playing ? "❚❚" : "▶"}</button>
      <input id="wb-week" type="range" min={7} max={25} step={1} value={maxWeek} aria-label="显示到孕周"
        onChange={e => { setPlaying(false); week.current = Number(e.target.value); setMaxWeek(Number(e.target.value)); }} />
      <span className="wb-week">GW{maxWeek}</span>
      {sample && <button className="wb-link" onClick={leave}>返回全树</button>}
    </div>
    <p className="wb-tree-source">{tree.source}</p>
  </section>;
}
