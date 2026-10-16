import {useEffect,useRef,useState} from 'react';
import type {PlaneHypothesis} from './types';

export default function MiniAnatomy({modelUrl,stage,planeHypothesis}:{modelUrl?:string;stage:string;planeHypothesis?:PlaneHypothesis}) {
  const host=useRef<HTMLDivElement>(null);
  const capture=useRef<(()=>string)|null>(null);
  const [ready,setReady]=useState(false);
  const [collapsed,setCollapsed]=useState(false),[status,setStatus]=useState('正在加载三维参照…');
  const planeKind=planeHypothesis?.kind,offset=planeHypothesis?.offset;
  useEffect(()=>{
    if(collapsed||!modelUrl)return;
    let active=true,dispose:(()=>void)|undefined;
    setStatus('正在加载三维参照…');setReady(false);capture.current=null;
    void import('../../anatomy/viewer').then(async ({createAnatomyViewer})=>{
      if(!active||!host.current)return;
      const viewer=createAnatomyViewer(host.current,()=>{});dispose=viewer.dispose;
      if(await viewer.load(modelUrl,stage)&&active){
        viewer.update({shell:.13,tissue:.48,solo:false,selected:'nt',rotate:false});
        viewer.positionCandidate(planeKind==='near_sagittal_model_landmark'&&stage==='CS15',offset??0);
        setStatus('');capture.current=()=>viewer.snapshot(1200);setReady(true);
      }
    }).catch(()=>{if(active){dispose?.();dispose=undefined;setStatus('二维联动可继续使用；3D 模型加载待恢复。');}});
    return()=>{active=false;capture.current=null;dispose?.();};
  },[modelUrl,stage,collapsed,planeKind,offset]);
  return <aside className="mini-anatomy" aria-label="解剖参照">
    <header><span>3D 解剖参照 <small>{stage}</small></span><button aria-label={collapsed?'展开三维参照':'折叠三维参照'}
      aria-expanded={!collapsed} onClick={()=>setCollapsed(v=>!v)}>{collapsed?'＋':'−'}</button></header>
    {!collapsed&&<>{modelUrl?<><div ref={host} className="mini-anatomy-viewport"/>{status&&<p role="status">{status}</p>}</>
      :<div className="mini-anatomy-empty">未配置三维模型</div>}
      {planeKind&&<p>候选切面</p>}
      {ready&&<details><summary>导出</summary><button type="button" aria-label="下载解剖参照 PNG" onClick={()=>{
        if(!capture.current)return;const link=document.createElement('a');link.href=capture.current();link.download='anatomy-reference-'+stage+'.png';link.click();
      }}>下载解剖参照 PNG</button></details>}</>}
  </aside>;
}
