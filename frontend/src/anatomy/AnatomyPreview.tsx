import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Box, RotateCcw, Plus, Minus, Play, Pause, Move3D } from 'lucide-react';
import { createAnatomyViewer, regions, type Region } from './viewer';
import { stages, type Stage } from './previewAssets';
import './preview.css';

export default function AnatomyPreview() {
  const host = useRef<HTMLDivElement>(null);
  const viewer = useRef<ReturnType<typeof createAnatomyViewer> | null>(null);
  const [stage, setStage] = useState<Stage>('CS15');
  const [selected, setSelected] = useState<Region>('nt');
  const [shell, setShell] = useState(13);
  const [tissue, setTissue] = useState(60);
  const [solo, setSolo] = useState(false);
  const [rotate, setRotate] = useState(false);
  const [status, setStatus] = useState('正在加载模型…');
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  const [candidate, setCandidate] = useState(true);
  const [offset, setOffset] = useState(0);
  const [evidence, setEvidence] = useState(false);
  const region = regions.find(r => r.id === selected)!;
  useEffect(() => {
    let current = true;
    setFailed(false); setStatus('正在加载模型…');
    try {
      const instance = createAnatomyViewer(host.current!, setSelected);
      viewer.current = instance;
      instance.load(stages[stage].file, stage).then(ok => { if (current && ok) setStatus('模型已就绪'); }).catch(() => {
        if (current) { setFailed(true); setStatus('模型未能加载，请检查连接后重试。'); }
      });
      return () => { current = false; instance.dispose(); viewer.current = null; };
    } catch {
      setFailed(true); setStatus('无法启动 3D 视图，请使用支持 WebGL 的浏览器。');
    }
  }, [stage, retry]);
  useEffect(() => {
    viewer.current?.update({ shell: shell / 100, tissue: tissue / 100, solo, selected, rotate });
  }, [stage, retry, shell, tissue, solo, selected, rotate]);
  useEffect(() => { viewer.current?.positionCandidate(candidate && stage === 'CS15', offset / 100); }, [candidate, offset, stage, retry]);
  return <main className="anatomy-app">
    <header className="topbar"><a className="brand" href="/anatomy.html"><Box size={22} strokeWidth={1.5}/> BRIDGE <span>/</span> <strong>发育解剖</strong></a><span className="preview-badge">组件预览</span></header>
    <div className="workspace">
      <section className="model-panel" aria-label="交互式发育解剖模型">
        <div className="model-heading"><div className="eyebrow">HUMAN DEVELOPMENT ATLAS</div><h1>从发育，看见结构。</h1><p>早期神经系统 · 真实胚胎三维重建</p></div>
        <div className="stage-tag"><span className="status-dot"/>{stage}<span>约 {stages[stage].days} 天 · 排卵后</span></div>
        <div className="canvas-host" ref={host}/>
        <div className="model-status" role="status" aria-live="polite">{status !== '模型已就绪' && <span>{status}</span>}{failed && <button onClick={() => setRetry(n => n + 1)}>重新加载</button>}</div>
        <div className="selection-label"><span style={{ background: region.color }}/><div><strong>{region.name}</strong><small>{region.en}</small></div></div>
        <div className="viewport-tools"><button title={rotate ? '暂停旋转' : '自动旋转'} aria-label={rotate ? '暂停旋转' : '自动旋转'} aria-pressed={rotate} onClick={() => setRotate(v => !v)}>{rotate ? <Pause size={17}/> : <Play size={17}/>}</button><i/><button title="放大" aria-label="放大" onClick={() => viewer.current?.zoom(0.85)}><Plus size={18}/></button><button title="缩小" aria-label="缩小" onClick={() => viewer.current?.zoom(1.15)}><Minus size={18}/></button><i/><button title="重置视角" aria-label="重置视角" onClick={() => viewer.current?.reset()}><RotateCcw size={17}/></button></div>
        <div className="interaction-hint"><Move3D size={15}/> 拖动旋转 · 滚轮缩放 · 点击结构</div>
      </section>
      <aside className="controls-panel">
        <section className="localization-controls"><div className="section-label">定位 <span>近矢状切面假设</span></div><p className="candidate-note">现有组织轮廓与矢状图谱头部相似。蓝色平面仅示意候选方向，未确定实际深度或细胞位置。</p><label className="isolate"><input type="checkbox" checked={candidate && stage === 'CS15'} disabled={stage !== 'CS15'} onChange={e => setCandidate(e.target.checked)}/>显示候选切面 · 待确认</label>{stage === 'CS15' ? <><label className="slider-label" htmlFor="plane-offset">参考模型横向偏移 <output>{offset > 0 ? '+' : ''}{offset}</output></label><input id="plane-offset" type="range" min="-70" max="70" value={offset} onChange={e => setOffset(+e.target.value)}/><div className="view-options"><button onClick={() => { setRotate(false); viewer.current?.faceCandidate(); }}>正对候选切面</button><button onClick={() => setOffset(0)}>回到参考中心</button></div><p className="stage-note">偏移为显示单位，不代表微米或切片序号。</p></> : <p className="stage-note">候选方向当前仅在 CS15 上示意。</p>}<button className="evidence-toggle" aria-expanded={evidence} onClick={() => setEvidence(v => !v)}>{evidence ? '收起切片对照' : '展开切片对照'}</button></section>
        <section><div className="section-label">01 <span>发育阶段</span></div><div className="stage-options">{(Object.keys(stages) as Stage[]).map(s => <button key={s} className={s === stage ? 'active' : ''} aria-pressed={s === stage} onClick={() => setStage(s)}><strong>{s}</strong><span>约 {stages[s].days} 天</span></button>)}</div><p className="stage-note">约 PCW5 / GW7 附近的解剖参照。<br/>阶段按形态划分，不能只凭周龄精确匹配。</p></section>
        <section><div className="section-label">02 <span>结构</span><small>点击高亮</small></div><div className="region-list">{regions.map(r => <button key={r.id} className={selected === r.id ? 'selected' : ''} aria-pressed={selected === r.id} onClick={() => setSelected(r.id)}><span className="swatch" style={{background:r.color}}/><span>{r.name}<small>{r.en}</small></span><span className="region-marker">{selected === r.id ? '●' : ''}</span></button>)}</div><label className="isolate"><input type="checkbox" checked={solo} onChange={e => setSolo(e.target.checked)}/>仅显示所选结构</label></section>
        <section><div className="section-label">03 <span>显示</span></div><label className="slider-label" htmlFor="shell">胚胎外层不透明度 <output>{shell}%</output></label><input id="shell" type="range" min="0" max="60" value={shell} disabled={solo} onChange={e => setShell(+e.target.value)}/><label className="slider-label" htmlFor="tissue">所选结构不透明度 <output>{tissue}%</output></label><input id="tissue" type="range" min="10" max="100" value={tissue} onChange={e => setTissue(+e.target.value)}/><div className="view-options"><button onClick={() => viewer.current?.reset('front')}>视角一</button><button onClick={() => viewer.current?.reset('side')}>视角二</button><button onClick={() => viewer.current?.reset()}>斜视角</button></div></section>
        <div className="anatomy-note"><strong>关于这份模型</strong><p>当前神经管包含早期脑与脊髓部分，尚无独立中脑分区。模型未与单细胞或空间数据配准。</p><a href={`https://hdbratlas.org/carnegie-stages/${stage}.html`} target="_blank" rel="noreferrer">HDBR 原始模型 · {stages[stage].specimen} <ArrowUpRight size={14}/></a></div>
      </aside>
    </div>
    {evidence && <section className="evidence-panel" aria-label="切片形态对照"><header><div><h2>切片与解剖参照</h2><p>上下摆放的是两张独立切片。对照用于提出方向假设，未做形变配准；各图比例不同。</p></div><span>未配准</span></header><div className="evidence-grid"><figure><img src="/anatomy-evidence/tissue.png" alt="既有空间坐标与 H&E 叠加图，上下摆放两张切片" onError={e => { e.currentTarget.hidden = true; }}/><figcaption>我们的切片 · 既有坐标叠加图<br/><small>图像由本地开发环境提供；原始全分辨率 H&E 尚缺。</small></figcaption></figure><figure><img src="/anatomy-evidence/sagittal.jpg" alt="HDBR CS15 N727 矢状切片 11" onError={e => { e.currentTarget.hidden = true; }}/><figcaption><a href="https://histology.hdbratlas.org/?config=/HDBR/config.json&image=11&model=N727" target="_blank" rel="noreferrer">HDBR CS15 · 矢状切片 N727 / 11 ↗</a><br/><small>优先比较头部弯曲腔隙及其内部组织轮廓。</small></figcaption></figure><figure><img src="/anatomy-evidence/frontal.jpg" alt="HDBR CS15 A352 冠状切片 24" onError={e => { e.currentTarget.hidden = true; }}/><figcaption><a href="https://histology.hdbratlas.org/?config=/HDBR/config.json&image=24&model=CS15_A352F" target="_blank" rel="noreferrer">HDBR CS15 · 冠状切片 A352 / 24 ↗</a><br/><small>保留为另一方向参照；单张图不能排除整个切面系列。</small></figcaption></figure></div><p className="evidence-limits">图谱切片与三维模型来自不同胚胎。蓝色平面依据模型双侧眼结构估计参考中心方向，不能作为我们的真实切片位置。尚需原始图像、方向地标和层序记录确认。</p></section>}
    <footer><span>HDBR Atlas · OPT 重建 · 几何与原始分区保留，显示颜色及透明度调整</span><a href="https://hdbratlas.org/copyright.html" target="_blank" rel="noreferrer">CC BY-NC-SA 4.0 · 来源与许可 ↗</a></footer>
  </main>;
}
