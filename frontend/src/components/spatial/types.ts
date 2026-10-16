import {object} from '../graphData';
export type SelectionKey = {kind:'type'|'subtype'|'cluster'; id:string};
export type Relation = {product_state_id:string; spatial_type_id:string; relation:'same_type'|'broader_type'; review_state:string; basis:string};
export type Group = {id:string; total:number; fraction:number; matched_types:string[]; unmatched_count:number; relations:Relation[];
  composition?:{type_id:string|null; count:number; fraction:number}[]};
export type Product = {n_observations:number; n_displayed:number; unknown_count:number; unassigned_counts?:Record<string,number>; qualified_assignment:boolean;
  records:{record_id:string; x:number; y:number; cluster:string; type_id:string|null; assignment_state?:string;reference_subtype_id?:string|null}[];
  reference_subtypes?:{source_label:string;single_source:true;resolved_count:number;groups:Group[];source_binding:unknown};
  types:Group[]; clusters:Group[]; sources:unknown[]};
export type PlaneHypothesis = {kind:'near_sagittal_model_landmark'; offset:number} | null;
export type Reference = {id:string; version:string; stage:string; n_observations:number; types:string[];
  sections:{id:string;label:string;n_observations:number;kind:'capture'}[];
  model_available:boolean; model_stage?:string; model_attribution?:string; model_license?:string; plane_hypothesis?:PlaneHypothesis};
export type LinkedContext = {kind:'linked_cell_context';version:'1.0';context_id:string;state:'available'|'unavailable';
  missing_reasons:string[]; product?:Product;reference?:Reference;crosswalk?:{version:string;entries:Relation[]}};
export type SpatialSection = {context_id:string;id:string;label:string;n_observations:number;
  coordinate_convention:'image_y_down'|'cartesian_y_up';types:string[];points:[number,number,number][];counts:Record<string,number>};
const finite=(n:unknown):n is number => typeof n==='number' && Number.isFinite(n);
const count=(n:unknown):n is number => Number.isSafeInteger(n) && Number(n)>=0;
const strings=(v:unknown):v is string[] => Array.isArray(v) && v.every(x=>typeof x==='string');
export function parseContext(v:unknown):LinkedContext|null {
  if (!object(v) || v.kind!=='linked_cell_context' || v.version!=='1.0' || typeof v.context_id!=='string' || !strings(v.missing_reasons)) return null;
  if (v.state==='unavailable') return v as LinkedContext;
  const p=v.product,r=v.reference;
  if(v.state!=='available'||!object(p)||!object(r)||!count(p.n_observations)||!count(p.unknown_count)
    ||!Array.isArray(p.records)||p.records.length>20000||!Array.isArray(p.types)||!Array.isArray(p.clusters)
    ||!Array.isArray(r.sections)||!r.sections.length||!strings(r.types)||!count(r.n_observations)) return null;
  if(!p.records.every(x=>object(x)&&finite(x.x)&&finite(x.y)&&typeof x.cluster==='string'&&(x.type_id===null||typeof x.type_id==='string'))
    || ![...p.types,...p.clusters].every(x=>object(x)&&typeof x.id==='string'&&count(x.total)&&count(x.unmatched_count)
      &&x.unmatched_count<=x.total&&finite(x.fraction)&&strings(x.matched_types)&&Array.isArray(x.relations))
    || !r.sections.every(x=>object(x)&&typeof x.id==='string'&&typeof x.label==='string'&&count(x.n_observations))) return null;
  if(p.unassigned_counts!==undefined&&(!object(p.unassigned_counts)||!Object.values(p.unassigned_counts).every(count)
    ||Object.values(p.unassigned_counts).reduce<number>((sum,n)=>sum+Number(n),0)!==p.unknown_count))return null;
  if(p.reference_subtypes!==undefined){
    const sub=p.reference_subtypes;
    const nObs=p.n_observations as number;
    const subtypeGroups=object(sub)&&Array.isArray(sub.groups)?sub.groups:[];
    const valid=object(sub)&&typeof sub.source_label==='string'&&sub.single_source===true
      &&count(sub.resolved_count)&&sub.resolved_count<=p.n_observations&&Array.isArray(sub.groups)
      &&sub.groups.every(g=>object(g)&&typeof g.id==='string'&&count(g.total)&&finite(g.fraction)
        &&Math.abs(g.fraction-g.total/nObs)<1e-9&&strings(g.matched_types)&&g.matched_types.length===0
        &&count(g.unmatched_count)&&g.unmatched_count===g.total&&Array.isArray(g.relations)&&g.relations.length===0)
      &&new Set(sub.groups.map(g=>g.id)).size===sub.groups.length
      &&sub.groups.reduce((n,g)=>n+g.total,0)+p.unknown_count===p.n_observations
      &&p.records.every(r=>r.type_id===null?r.reference_subtype_id===null:
        typeof r.reference_subtype_id==='string'&&subtypeGroups.some(g=>g.id===r.reference_subtype_id));
    if(!valid)return {...v,product:{...p,reference_subtypes:undefined}} as LinkedContext;
  }
  return v as LinkedContext;
}
export function parseSection(v:unknown):SpatialSection|null {
  if(!object(v)||typeof v.id!=='string'||typeof v.context_id!=='string'||!count(v.n_observations)||!strings(v.types)
    ||!['image_y_down','cartesian_y_up'].includes(String(v.coordinate_convention))||!object(v.counts)||!Array.isArray(v.points)
    ||v.points.length!==v.n_observations||!v.points.every(p=>Array.isArray(p)&&p.length===3&&finite(p[0])&&finite(p[1])
      &&count(p[2])&&p[2]< (v.types as string[]).length)) return null;
  if(!v.types.every(t=>count((v.counts as Record<string,unknown>)[t]))
    || v.types.reduce((sum,t)=>sum+Number((v.counts as Record<string,unknown>)[t]),0)!==v.n_observations) return null;
  return v as SpatialSection;
}
const colors=['#E6A087','#75BEC9','#AC98C9','#C7A575','#79BDA7','#CF8FA9','#85A9CB','#CDB16A'];
// Stable identity colors for the shared product/reference vocabulary. Never hash these categories into collisions.
const typeColors:Record<string,string>={'Radial Glia':'#79BDA7','Neuroblast':'#E6A087','Neuron Glut':'#85A9CB',
  'Neuron GABA':'#AC98C9','Neuron Sero':'#CDB16A','Neuron DA':'#CF8FA9','Neuron OMTN':'#75BEC9',
  'Astrocyte':'#7197BB','Endothelial Cell':'#97B879','Fibroblast':'#B986A1','Glioblast':'#69A8A0',
  'Immune Cell':'#B7B070','Neuron ChAT':'#9384B5','Neuron Glut GABA':'#C29AC1','Oligo':'#B68D75',
  'OPC':'#709A80','Pericyte':'#C7A575','Smooth Muscle':'#9BA5C8','RG mFP':'#79BDA7','RG dHyp':'#A9CBB7','RG mBIP':'#609F94','Nb mFP':'#E6A087','Nb mAP':'#D3A5B5','Nb mBMP':'#E9BE8F','IPC m1':'#BCA8CE'};
export function colorFor(id:string):string {const label=id.replace(/^L[12]:/,'').replaceAll('_',' ');
  if(typeColors[label])return typeColors[label];let h=0;for(const c of id)h=(h*31+c.charCodeAt(0))>>>0;return colors[h%colors.length];}
export const sameKey=(a:SelectionKey|null,b:SelectionKey|null)=>a?.kind===b?.kind&&a?.id===b?.id;
