import { CHAIN_NAMES, CHAIN_SHORT, LOW_LEVEL } from "./stages";

/** Five concentric arcs for the differentiation chain; low levels use the warning tone. */
export function ChainRings({ values, size = 170 }: { values: readonly (number | null)[]; size?: number }) {
  const sweep = Math.PI * 1.75, start = -Math.PI / 2;
  const point = (r: number, angle: number) => [90 + r * Math.cos(angle), 90 + r * Math.sin(angle)].map(v => v.toFixed(2)).join(" ");
  return <svg className="wb-rings" viewBox="0 0 180 180" width={size} height={size} role="img"
    aria-label={values.map((v, i) => `${CHAIN_NAMES[i]} ${v === null ? "未测量" : `${Math.round(v * 100)}%`}`).join("，")}>
    {values.map((value, i) => {
      const r = 78 - i * 13, low = value !== null && value < LOW_LEVEL, end = start + Math.max(0.001, value ?? 0) * sweep;
      return <g key={i} className={value === null ? "wb-ring wb-ring--missing" : low ? "wb-ring wb-ring--low" : "wb-ring"}>
        <path d={`M${point(r, start)} A${r} ${r} 0 1 1 ${point(r, start + sweep)}`} className="wb-ring-track" />
        {value !== null && <path d={`M${point(r, start)} A${r} ${r} 0 ${value > 0.571 ? 1 : 0} 1 ${point(r, end)}`} className="wb-ring-value"><title>{`${CHAIN_NAMES[i]} ${Math.round(value * 100)}%`}</title></path>}
        <text x="86" y={90 - r + 3.5} textAnchor="end">{CHAIN_SHORT[i]}</text>
      </g>;
    })}
  </svg>;
}
