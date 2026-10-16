import { useEffect, useRef, useState } from "react";

export type LogoItem = { id: string; label: string; hint?: string; onSelect: () => void };

/**
 * The BRIDGE mark: one glass cell whose nucleus leans toward the pointer. With menu items it is a button;
 * opening divides the cell in two, joined by a strand (the bridge), and unfolds the menu.
 */
export function CellLogo({ items = [], size = 38 }: { items?: LogoItem[]; size?: number }) {
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null), nucleus = useRef<HTMLSpanElement>(null), menu = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let frame = 0;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    const follow = (e: PointerEvent) => {
      if (reduce?.matches) return;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const host = button.current ?? nucleus.current?.parentElement, box = host?.getBoundingClientRect();
        if (!box || !nucleus.current) return;
        const dx = e.clientX - (box.left + box.width / 2), dy = e.clientY - (box.top + box.height / 2), d = Math.hypot(dx, dy) || 1, k = Math.min(1, 200 / d);
        nucleus.current.style.transform = `translate(${dx / d * k * size * .1}px, ${dy / d * k * size * .1}px)`;
      });
    };
    window.addEventListener("pointermove", follow);
    return () => { window.removeEventListener("pointermove", follow); cancelAnimationFrame(frame); };
  }, [size]);
  useEffect(() => {
    if (!open) return;
    menu.current?.querySelector<HTMLButtonElement>("[role=menuitem]")?.focus();
    const close = (e: Event) => { if (!menu.current?.contains(e.target as Node) && !button.current?.contains(e.target as Node)) setOpen(false); };
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setOpen(false); button.current?.focus(); }
      if (e.key === "Tab") { setOpen(false); return; }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        const list = [...(menu.current?.querySelectorAll<HTMLButtonElement>("[role=menuitem]") ?? [])], i = list.indexOf(document.activeElement as HTMLButtonElement);
        list[(i + (e.key === "ArrowDown" ? 1 : list.length - 1)) % list.length]?.focus(); e.preventDefault();
      }
    };
    window.addEventListener("pointerdown", close); window.addEventListener("keydown", key);
    return () => { window.removeEventListener("pointerdown", close); window.removeEventListener("keydown", key); };
  }, [open]);
  const style = { width: size, height: size };
  const cell = <><span className="cell-logo-strand" /><span className="cell-logo-twin" /><span ref={nucleus} className="cell-logo-nucleus" /></>;
  if (!items.length) return <span className="cell-logo" style={style} aria-hidden="true">{cell}</span>;
  return <span className="cell-logo-wrap">
    <button ref={button} type="button" className="cell-logo" style={style} aria-label="BRIDGE 菜单" aria-haspopup="menu" aria-expanded={open}
      onKeyDown={e => { if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); setOpen(true); } }}
      onClick={() => setOpen(o => !o)}>{cell}</button>
    <div ref={menu} className={`cell-logo-menu${open ? " cell-logo-menu--open" : ""}`} role="menu" aria-label="BRIDGE" hidden={!open}>
      {items.map(item => <button key={item.id} type="button" role="menuitem" onClick={() => { setOpen(false); button.current?.focus(); item.onSelect(); }}>
        {item.label}{item.hint && <small>{item.hint}</small>}</button>)}
    </div>
  </span>;
}
