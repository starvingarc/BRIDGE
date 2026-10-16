import type { CSSProperties } from "react";

// Decorative cell forms identify a workspace, never a scientific measurement.
export function ResearchCover({variant = false}: {variant?: boolean}) {
  const cells = variant
    ? [[25,27,56,-15],[75,40,47,26],[47,82,54,-12],[104,83,26,5],[27,93,21,-8]]
    : [[36,27,47,-8],[88,47,36,13],[56,75,56,16],[24,74,30,-10],[95,108,25,16],[111,81,19,5],[39,120,16,-5]];
  return <div className="research-cover" aria-hidden="true"><div className={`research-dish ${variant ? "research-dish--neutral" : ""}`}>
    {cells.map(([x,y,size,angle], index) => <span key={index} className="research-cell" style={{
      "--cell-x": x + "px", "--cell-y": y + "px", "--cell-size": size + "px", "--cell-angle": angle + "deg",
    } as CSSProperties} />)}
  </div></div>;
}

export function ResearchBrand() {
  return <div className="research-brand"><span className="research-brand-orb" aria-hidden="true" />
    <div><span>BRIDGE</span><small>研究工作台</small></div>
  </div>;
}
