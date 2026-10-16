import type { CSSProperties } from "react";
import { stageOf } from "./stages";
import type { Protocol } from "./types";

/** The eight dish illustrations (docs/assets/culture-dish-artwork.md); decorative, never a measurement. */
export type DishArt =
  | "not-started" | "expansion" | "stage-i-neural-induction" | "stage-ii-floor-plate-induction"
  | "stage-iii-floor-plate-progenitor" | "stage-iv-neuronal-maturation" | "cryopreserved" | "post-graft";

const BY_STAGE: DishArt[] = ["expansion", "stage-i-neural-induction", "stage-ii-floor-plate-induction", "stage-iii-floor-plate-progenitor", "stage-iv-neuronal-maturation"];
/** Each illustration moves in its own way; frozen and empty dishes stay still. */
const MOTION: Record<DishArt, string> = {
  "not-started": "still", expansion: "breathe", "stage-i-neural-induction": "sway", "stage-ii-floor-plate-induction": "sway",
  "stage-iii-floor-plate-progenitor": "drift", "stage-iv-neuronal-maturation": "fire", cryopreserved: "still", "post-graft": "glow",
};

export const artForStage = (index: number): DishArt => BY_STAGE[Math.max(0, Math.min(4, index))];

export function artFor(protocol: Protocol): DishArt {
  if (protocol.state === "draft") return "not-started";
  if (protocol.state === "frozen") return "cryopreserved";
  if (protocol.state === "grafted") return "post-graft";
  return artForStage(stageOf(protocol).index);
}

const artUrl = (art: DishArt) => `${import.meta.env.BASE_URL}illustrations/culture-dishes/${art}.svg`;
/** Spreads animation phases so a shelf of dishes does not pulse in step. */
const delay = (key: string) => -(key.split("").reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % 7);

/**
 * A culture dish. `live` adds a slow glass sheen for cultures that are growing now;
 * without `size` the dish fills its container's width.
 */
export function CultureDish({ art, size, keyId, live = false }: { art: DishArt; size?: number; keyId: string; live?: boolean }) {
  const style = { "--wb-dish-delay": `${delay(keyId)}s`, ...(size ? { width: size, height: size } : {}) } as CSSProperties;
  return <span className={`wb-dish wb-dish--${MOTION[art]}${live ? " wb-dish--live" : ""}`} style={style} data-art={art} aria-hidden="true">
    <img src={artUrl(art)} alt="" draggable={false} decoding="async" />
  </span>;
}

/** Dish for a protocol stage node (0 expansion … 4 maturation), independent of a specific culture. */
export function StageDish({ stage, size, keyId, live = false }: { stage: number; size?: number; keyId: string; live?: boolean }) {
  return <CultureDish art={artForStage(stage)} size={size} keyId={keyId} live={live} />;
}
