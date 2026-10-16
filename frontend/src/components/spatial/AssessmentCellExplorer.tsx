import {useEffect,useState,type ReactNode} from 'react';
import {object} from '../graphData';
import {readBoundedText} from '../ResultsPane';
import LinkedCellExplorer from './LinkedCellExplorer';

type Binding={state:'available';umap_artifact_id:string;binding_token:string;candidate_receipt_sha256:string}|{state:'unavailable'};
export default function AssessmentCellExplorer({sessionId,scopeDigest,evidenceAlias,fallback}:{
  sessionId:string;scopeDigest:string;evidenceAlias:string;fallback:ReactNode;
}) {
  const url='/api/sessions/'+encodeURIComponent(sessionId)+'/assessment/cell-explorer?scope_digest='+encodeURIComponent(scopeDigest)+'&evidence_alias='+encodeURIComponent(evidenceAlias);
  const [result,setResult]=useState<{url:string;binding:Binding}|null>(null);
  useEffect(()=>{const controller=new AbortController();
    void (async()=>{let binding:Binding={state:'unavailable'};
      try{const response=await fetch(url,{credentials:'same-origin',signal:controller.signal});
        if(response.ok){const body=await readBoundedText(response,16000);const data=body.truncated?null:JSON.parse(body.text);
          if(object(data)&&data.state==='available'&&typeof data.umap_artifact_id==='string'&&typeof data.binding_token==='string'
            && typeof data.candidate_receipt_sha256==='string' && /^[a-f0-9]{64}$/.test(data.candidate_receipt_sha256))binding=data as Binding;}
      }catch{/* Existing composition remains available when linkage cannot be verified. */}
      if(!controller.signal.aborted)setResult({url,binding});})();
    return()=>controller.abort();
  },[url]);
  if(result?.url!==url)return <>{fallback}<p role="status">正在加载细胞表达谱与空间参考…</p></>;
  return result.binding.state==='available'
    ?<LinkedCellExplorer key={url+result.binding.binding_token} sessionId={sessionId} umapArtifactId={result.binding.umap_artifact_id} expectedCandidateReceiptSha256={result.binding.candidate_receipt_sha256} showComposition fallback={fallback}/>
    :<>{fallback}<p className="chart-meta">细胞表达谱与空间参考暂不可用。</p></>;
}
