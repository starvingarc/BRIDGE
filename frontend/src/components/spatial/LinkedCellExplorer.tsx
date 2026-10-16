import {useCallback,useEffect,useMemo,useRef,useState,type ReactNode} from 'react';
import {createPortal} from 'react-dom';
import ExpressionUMAP,{ProductScatter} from '../ExpressionUMAP';
import {readBoundedText} from '../ResultsPane';
import {object} from '../graphData';
import SpatialScatter from './SpatialScatter';
import MiniAnatomy from './MiniAnatomy';
import CompositionChart from './CompositionChart';
import {colorFor,parseContext,parseSection,sameKey} from './types';
import type {Group,LinkedContext,SelectionKey,SpatialSection} from './types';
import './linked-cell-explorer.css';

const reasons:Record<string,string>={spatial_reference_not_configured:'空间参考暂不可用。',
  same_view_candidate_assignments_missing:'当前产品视图尚无可连接的候选注释。',
  same_view_candidate_assignments_ambiguous:'当前产品视图有多份候选注释，需明确选择对应版本。'};
async function readJson(response:Response,limit:number){if(!response.ok)throw new Error('unavailable');
  const body=await readBoundedText(response,limit);if(body.truncated)throw new Error('too_large');return JSON.parse(body.text) as unknown;}

export default function LinkedCellExplorer({sessionId,umapArtifactId,showComposition=false,fallback,expectedCandidateReceiptSha256}:{sessionId:string;umapArtifactId:string;showComposition?:boolean;fallback?:ReactNode;expectedCandidateReceiptSha256?:string}){
  const url='/api/sessions/'+encodeURIComponent(sessionId)+'/artifacts/'+encodeURIComponent(umapArtifactId);
  const requestKey=url+'|'+(expectedCandidateReceiptSha256??'');
  const [result,setResult]=useState<{requestKey:string;data:LinkedContext|null}|null>(null);
  const [generation,setGeneration]=useState(0);
  useEffect(()=>{const controller=new AbortController();
    void fetch(url+'/spatial-context',{credentials:'same-origin',signal:controller.signal})
      .then(r=>readJson(r,24_000_000)).then(parseContext).catch(()=>null)
      .then(data=>{if(!controller.signal.aborted)setResult({requestKey,data});});
    return()=>controller.abort();
  },[url,requestKey,generation]);
  if(result?.requestKey!==requestKey)return <p role="status">正在核对产品与空间参考来源…</p>;
  const context=result.data;
  // The display contract orders coordinate then assignment source bindings.
  // Keep the assessment's exact candidate receipt pinned across every reload.
  const assignmentSource=context?.product?.sources?.[1];
  if(expectedCandidateReceiptSha256!==undefined && context?.state==='available'
      && (!object(assignmentSource) || assignmentSource.receipt_sha256!==expectedCandidateReceiptSha256))return <section>
    <p role="status">细胞注释版本已更新，请重新打开此评估结果。</p>{fallback}</section>;
  if(!context||context.state!=='available'||!context.product||!context.reference)return <section>
    <p role="status">{reasons[context?.missing_reasons[0]??'']??'空间联动暂不可用，请核对数据来源。'}</p>
    {fallback}<ExpressionUMAP url={url}/></section>;
  return <LinkedView key={url+context.context_id} context={context} url={url} showComposition={showComposition} reload={()=>{setResult(null);setGeneration(n=>n+1);}}/>;
}
function LinkedView({context,url,reload,showComposition}:{context:LinkedContext;url:string;reload:()=>void;showComposition:boolean}){
  const product=context.product!,reference=context.reference!;
  const [expanded,setExpanded]=useState(false);
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{if(expanded)dialog.current?.showModal();},[expanded]);
  const [mode,setMode]=useState<'type'|'subtype'|'cluster'>('type');
  const [hoverKey,setHoverKey]=useState<SelectionKey|null>(null),[pinnedKey,setPinnedKey]=useState<SelectionKey|null>(null);
  const [sectionId,setSectionId]=useState(reference.sections[0].id);
  const [sectionResult,setSectionResult]=useState<{id:string;data:SpatialSection|null;stale:boolean}|null>(null);
  const [refresh,setRefresh]=useState(0);
  useEffect(()=>{const controller=new AbortController();const expected=context.context_id;
    void (async()=>{let data:SpatialSection|null=null,stale=false;
      try{const response=await fetch(url+'/spatial-context/sections/'+encodeURIComponent(sectionId)+'?context_id='+encodeURIComponent(expected),
        {credentials:'same-origin',signal:controller.signal});stale=response.status===409;
        data=parseSection(await readJson(response,64_000_000));
        if(data?.context_id!==expected||data.id!==sectionId)data=null;
      }catch{/* Explicit unavailable state below. */}
      if(!controller.signal.aborted)setSectionResult({id:sectionId,data,stale});})();
    return()=>controller.abort();
  },[url,context.context_id,sectionId,refresh]);
  const activeKey=pinnedKey??hoverKey;
  const preview=useCallback((key:SelectionKey|null)=>{
    if(!pinnedKey)setHoverKey(previous=>sameKey(previous,key)?previous:key);
  },[pinnedKey]);
  const compositionMode=mode==='subtype'?'subtype':'type';
  const compositionGroups=compositionMode==='subtype'?product.reference_subtypes?.groups??product.types:product.types;
  const groups=mode==='cluster'?product.clusters:compositionGroups;
  const list=useMemo(()=>{
    const counts=product.unassigned_counts??{unknown:product.unknown_count};
    const unknown:Group[]=Object.entries(counts).filter(([,n])=>n>0).map(([state,n])=>({id:state==='unavailable'?'__unavailable__':'__unknown__',total:n,fraction:n/product.n_observations,matched_types:[],unmatched_count:n,relations:[]}));
    return mode!=='cluster'?[...groups,...unknown]:groups;
  },[groups,mode,product]);
  const active=activeKey?.kind===mode?list.find(g=>g.id===activeKey.id):undefined;
  const activeTypes=useMemo(()=>active?.matched_types??[],[active]);
  const palette=useMemo(()=>Object.fromEntries(reference.types.map(id=>[id,colorFor(id)])),[reference.types]);
  const productPalette=useMemo(()=>Object.fromEntries(list.map(g=>[g.id,g.id==='__unknown__'?'#b8c1c8':g.id==='__unavailable__'?'#687680':colorFor(g.id)])),[list,mode,palette]);
  const section=sectionResult?.id===sectionId?sectionResult.data:null;
  const label=(id:string)=>id==='__unknown__'?'未确定分配':id==='__unavailable__'?'不可用分配':id.replace(/^L[12]:/,'').replaceAll('_',' ');
  const pin=(key:SelectionKey)=>{setPinnedKey(previous=>sameKey(previous,key)?null:key);setHoverKey(null);};
  const clear=()=>{setPinnedKey(null);setHoverKey(null);};
  const view=<section className="linked-cell-explorer" aria-label="产品与空间参考联动" onKeyDown={e=>{if(e.key==='Escape'&&activeKey){clear();e.preventDefault();e.stopPropagation();}}}>
    <header className="linked-heading"><div><h3>细胞组成与空间分布</h3></div>
      <div className="linked-heading-actions">
      <button onClick={()=>setExpanded(v=>!v)}>{expanded?'收起联动视图':'放大联动视图'}</button></div></header>
    <div className={"linked-figures"+(showComposition?" with-composition":"")} >
    {showComposition&&<div className="linked-composition"><CompositionChart rows={[
      ...compositionGroups.map(g=>({id:g.id,label:label(g.id),count:g.total,denominator:product.n_observations,fraction:g.fraction})),
      ...Object.entries(product.unassigned_counts??{unknown:product.unknown_count}).filter(([,n])=>n>0).map(([state,count])=>({id:state==='unavailable'?'__unavailable__':'__unknown__',label:state==='unavailable'?'不可用分配':'未确定分配',count,denominator:product.n_observations,fraction:count/product.n_observations,state})),
    ]} showTable={false} classificationLabel={compositionMode==='subtype'?'参考亚型':'细胞类型'} palette={Object.fromEntries(compositionGroups.map(g=>[g.id,colorFor(g.id)]))} activeId={activeKey?.kind===compositionMode?activeKey.id:null}
      onHover={id=>{if(mode!=='cluster')preview(id?{kind:compositionMode,id}:null);}} onPin={id=>{setMode(compositionMode);pin({kind:compositionMode,id});}}/></div>}
    <section className="linked-product"><header><h4>细胞表达谱分布</h4>
      <label><select aria-label="产品分组方式" value={mode} onChange={e=>{setMode(e.target.value as 'type'|'subtype'|'cluster');clear();}}>
        <option value="type">细胞类型</option>{product.reference_subtypes&&<option value="subtype">参考亚型</option>}<option value="cluster">细胞簇</option></select></label></header>
      <div className="linked-plot-with-legend"><div className="linked-counted-plot"><ProductScatter data={product} activeKey={activeKey} mode={mode} palette={productPalette} onHover={preview} onPin={pin}/>
      <span className="linked-plot-count">n={product.n_displayed.toLocaleString()}{product.n_displayed!==product.n_observations&&<> / {product.n_observations.toLocaleString()}</>}</span>
      {active&&!pinnedKey&&<span className="linked-hover-label" aria-live="polite" data-testid="linked-preview">{label(active.id)}</span>}</div>
      <div className="linked-group-list" aria-label="产品类别">{list.map(g=><button key={g.id} aria-pressed={sameKey(pinnedKey,{kind:mode,id:g.id})}
        onMouseEnter={()=>preview({kind:mode,id:g.id})} onMouseLeave={()=>preview(null)}
        onFocus={()=>preview({kind:mode,id:g.id})} onBlur={()=>preview(null)} onClick={()=>pin({kind:mode,id:g.id})}>
        <i style={{background:productPalette[g.id]}}/><span>{label(g.id)} · {g.total.toLocaleString()}</span><small>{(g.fraction*100).toFixed(2)}%</small></button>)}</div></div>
    </section><section className="linked-reference"><div className="linked-reference-top"><div><h4>空间分布</h4><p>{reference.stage}</p>
      <label><select aria-label="空间捕获单元" value={sectionId} onChange={e=>setSectionId(e.target.value)}>{reference.sections.map(s=><option key={s.id} value={s.id}>{s.label}</option>)}</select></label>
      </div></div><div className="linked-reference-body"><div className="linked-spatial-main">
      {section?<SpatialScatter section={section} activeTypeIds={activeTypes} palette={palette}/>:<p role="status">{sectionResult?.id!==sectionId?'正在加载空间坐标…':
        sectionResult.stale?'数据版本已更新，请重新打开此结果。':'空间坐标暂不可用。'}</p>}
      {sectionResult?.id===sectionId&&sectionResult.stale&&<button onClick={reload}>重新加载当前版本</button>}
      {sectionResult?.id===sectionId&&!section&&!sectionResult.stale&&<button onClick={()=>setRefresh(n=>n+1)}>重试空间坐标</button>}
    </div><MiniAnatomy modelUrl={reference.model_available?url+'/spatial-context/model?context_id='+encodeURIComponent(context.context_id):undefined}
        stage={reference.model_stage??reference.stage} planeHypothesis={reference.plane_hypothesis}/></div>
    </section></div>
    {active&&pinnedKey&&<div className="linked-selection" aria-live="polite" data-testid="linked-selection"><strong>{'已锁定 '+label(active.id)}</strong>
      {active&&<><span>n={active.total.toLocaleString()} / {product.n_observations.toLocaleString()}
        {activeTypes.length>0&&active.unmatched_count>0&&<> · 类型对应 {(active.total-active.unmatched_count).toLocaleString()} / {active.total.toLocaleString()}</>}</span>
        <button onClick={clear}>清除选择</button></>}
      {active&&mode==='subtype'?<p>空间匹配层级：细胞类型。<button onClick={()=>{setMode('type');clear();}}>查看类型分布</button></p>:
        active&&['__unknown__','__unavailable__'].includes(active.id)?<p>空间对应需要明确的类型标签。</p>:
        active&&!activeTypes.length?<p>空间对应待确认。</p>:null}
      {active?.composition&&<p>{active.composition.map(row=>label(row.type_id??'__unknown__')+'：'+row.count+'（'+(100*row.fraction).toFixed(2)+'%）').join(' · ')}</p>}
      {active?.relations.some(r=>r.relation==='broader_type')&&<p>空间匹配层级：细胞类型。</p>}
    </div>}
    <details className="linked-sources"><summary>数据与来源</summary>
      <button type="button" disabled={!section} onClick={()=>{if(!section)return;
        const payload={context,section,selectedKey:activeKey,palette,productPalette};
        const href=URL.createObjectURL(new Blob([JSON.stringify(payload)],{type:'application/json'}));
        const link=document.createElement('a');link.href=href;link.download='cell-composition-figure-data.json';link.click();
        setTimeout(()=>URL.revokeObjectURL(href),1000);
      }}>下载绘图数据</button><p>对应表版本 {context.crosswalk?.version} · 空间参考版本 {reference.version}</p>
      <p>降维方法：UMAP</p>
      <p>细胞标签用于描述候选组成；空间图按已建立的类别对应展示。</p>
      {product.reference_subtypes&&<p>参考亚型来源：{product.reference_subtypes.source_label} · {product.reference_subtypes.resolved_count.toLocaleString()} 个细胞具有细分标签。</p>}
      {reference.model_attribution&&<p>3D 模型：{reference.model_attribution} · {reference.model_license}</p>}
      </details>
  </section>;
  return expanded?createPortal(<dialog ref={dialog} className="linked-dialog" aria-label="放大的产品与空间联动"
    onCancel={()=>setExpanded(false)}>{view}</dialog>,document.body):view;
}
