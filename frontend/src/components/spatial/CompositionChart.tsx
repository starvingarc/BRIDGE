import {useId, useMemo} from 'react';
export type CompositionBar = {id:string; label:string; count:number; denominator:number; fraction:number; state?:string; selectionId?:string};
const percent=(value:number)=>new Intl.NumberFormat('en',{style:'percent',maximumFractionDigits:2}).format(value);

/** Full-denominator counts only; the shared selection never filters the denominator. */
export default function CompositionChart({rows,palette={},activeId,onHover,onPin,showTable=true,classificationLabel="候选分类"}:{rows:CompositionBar[];palette?:Record<string,string>;
  classificationLabel?:string;showTable?:boolean;activeId?:string|null;onHover?:(id:string|null)=>void;onPin?:(id:string)=>void}) {
  const pattern=useId().replaceAll(':','');
  const ordered=useMemo(()=>[...rows].sort((a,b)=>b.fraction-a.fraction),[rows]);
  const width=Math.max(600,ordered.length*66+70),height=338,left=48,top=24,bottom=232;
  const step=(width-left-18)/Math.max(1,ordered.length),barWidth=Math.min(42,step*.66);
  const y=(fraction:number)=>bottom-fraction*(bottom-top);
  return <figure className="composition-figure" aria-label="候选细胞组成图">
    <figcaption><strong>细胞组成</strong><span>{classificationLabel} · n = {rows[0]?.denominator.toLocaleString() ?? '—'}</span></figcaption>
    <div className="composition-svg-scroll"><svg xmlns="http://www.w3.org/2000/svg" viewBox={`0 0 ${width} ${height}`} style={{minWidth:Math.min(width,600)}}
      role="group" aria-label="各候选类别占全部细胞的比例，纵轴为0至100%">
      <defs><pattern id={pattern} width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="5" height="5" fill="#dce0e3"/><line x1="0" y1="0" x2="0" y2="5" stroke="#687680" strokeWidth="2"/></pattern></defs>
      {[0,.25,.5,.75,1].map(t=><g key={t} aria-hidden="true"><line x1={left} x2={width-12} y1={y(t)} y2={y(t)} stroke={t?'#e5e8eb':'#5c6570'} strokeWidth={t?.65:1}/><text x={left-9} y={y(t)+4} textAnchor="end" fontSize="11" fill="#424b57">{t*100}</text></g>)}
      <text x="14" y="18" fontSize="11" fill="#424b57">%</text>
      {ordered.map((row,i)=>{const x=left+step*(i+.5),id=row.selectionId??row.id,active=activeId===id;
        const fill=row.state==='unknown'?`url(#${pattern})`:row.state==='unavailable'?'#77838b':palette[row.id]??'#357f86';
        return <g key={row.id} role={onPin?'button':'img'} tabIndex={onPin?0:undefined} aria-pressed={onPin?active:undefined}
          aria-label={`${row.label}: ${percent(row.fraction)}, ${row.count} / ${row.denominator}`} className="composition-bar"
          onMouseEnter={()=>onHover?.(id)} onMouseLeave={()=>onHover?.(null)} onFocus={()=>onHover?.(id)} onBlur={()=>onHover?.(null)}
          onClick={()=>onPin?.(id)} onKeyDown={event=>{if(onPin&&['Enter',' '].includes(event.key)){event.preventDefault();onPin(id);}}}>
          <title>{row.label}: {row.count} / {row.denominator}</title>
          <rect x={x-step/2} y={top} width={step} height={height-top} fill="transparent"/>
          <rect x={x-barWidth/2} y={y(row.fraction)} width={barWidth} height={row.fraction*(bottom-top)} fill={fill}
            stroke={active?'#172b3a':'#fff'} strokeWidth={active?2:.6} opacity={activeId&&!active ? .3:1}/>
          <text x={x} y={y(row.fraction)-7} textAnchor="middle" fontSize="11" fill="#26343e">{percent(row.fraction)}</text>
          <text transform={`translate(${x+2},${bottom+17}) rotate(-42)`} textAnchor="end" fontSize="11" fill="#26343e">{row.label}</text>
        </g>;
      })}
    </svg></div>
    {showTable&&<details><summary>细胞数与比例</summary><table><thead><tr><th>候选类别</th><th>细胞数 / 总数</th><th>比例</th></tr></thead><tbody>{ordered.map(row=><tr key={row.id}><th scope="row">{row.label}</th><td>{row.count} / {row.denominator}</td><td>{percent(row.fraction)}</td></tr>)}</tbody></table></details>}
  </figure>;
}
