import {useEffect,useMemo,useRef} from 'react';
import type {SpatialSection} from './types';

export default function SpatialScatter({section,activeTypeIds,palette}:{section:SpatialSection;activeTypeIds:string[];palette:Record<string,string>}) {
  const background=useRef<HTMLCanvasElement>(null),foreground=useRef<HTMLCanvasElement>(null);
  const positions=useMemo(()=>{
    let left=Infinity,right=-Infinity,top=Infinity,bottom=-Infinity;
    for(const [x,y] of section.points){left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);}
    const scale=Math.min(700/(right-left||1),440/(bottom-top||1));
    const index=new Map<string,number[]>();
    const xy=new Float32Array(section.points.length*2);
    section.points.forEach(([x,y,t],i)=>{xy[i*2]=380+(x-(left+right)/2)*scale;
      xy[i*2+1]=250+(y-(top+bottom)/2)*scale*(section.coordinate_convention==='image_y_down'?1:-1);
      const label=section.types[t]; if(!index.has(label))index.set(label,[]);index.get(label)!.push(i);});
    return {xy,index};
  },[section]);
  useEffect(()=>{const ctx=background.current?.getContext('2d');if(!ctx)return;
    ctx.clearRect(0,0,760,500);ctx.fillStyle='#cdd3d0';ctx.globalAlpha=.5;
    for(let i=0;i<positions.xy.length;i+=2)ctx.fillRect(positions.xy[i],positions.xy[i+1],1.3,1.3);
    ctx.globalAlpha=1;
  },[positions]);
  useEffect(()=>{const ctx=foreground.current?.getContext('2d');if(!ctx)return;
    ctx.clearRect(0,0,760,500);ctx.globalAlpha=.9;
    for(const id of activeTypeIds){ctx.fillStyle=palette[id]??'#357f86';
      for(const i of positions.index.get(id)??[])ctx.fillRect(positions.xy[i*2]-.4,positions.xy[i*2+1]-.4,2,2);}
    ctx.globalAlpha=1;
  },[positions,activeTypeIds,palette]);
  const matched=activeTypeIds.reduce((sum,id)=>sum+(section.counts[id]??0),0);
  return <><div className="linked-plot-with-legend"><div className="spatial-canvas-stack" role="img" aria-label="空间参考原始坐标；灰色为全部观测，彩色为匹配类型">
    <canvas ref={background} width={760} height={500}/><canvas ref={foreground} width={760} height={500}/>
      <span className="linked-plot-count" data-testid="spatial-count">n={activeTypeIds.length>0&&<>{matched.toLocaleString()} / </>}{section.n_observations.toLocaleString()}</span></div>
    <div className="linked-legend" aria-label="空间图例"><span><i style={{background:'#cdd3d0'}}/>全部空间点</span>
      {activeTypeIds.map(id=><span key={id}><i style={{background:palette[id]}}/>{id.replaceAll('_',' ')} · {(section.counts[id]??0).toLocaleString()}</span>)}</div></div>
    </>;
}
