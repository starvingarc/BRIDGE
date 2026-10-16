import { useEffect, useRef } from "react";

/** Runs callback on every animation frame while active. */
export function useFrame(callback: (now: number) => void, active = true) {
  const latest = useRef(callback);
  latest.current = callback;
  useEffect(() => {
    if (!active || typeof requestAnimationFrame !== "function") return;
    let id = 0;
    const tick = (now: number) => { latest.current(now); id = requestAnimationFrame(tick); };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
  }, [active]);
}

export const prefersMotion = () =>
  typeof matchMedia !== "function" || !matchMedia("(prefers-reduced-motion: reduce)").matches;
