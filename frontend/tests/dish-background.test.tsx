import { fireEvent, render } from "@testing-library/react";
import { DishBackground } from "../src/components/DishBackground";

function setup(reduced: boolean) {
  class TestPointerEvent extends MouseEvent {
    pointerId: number;
    constructor(type: string, init: PointerEventInit = {}) { super(type, init); this.pointerId = init.pointerId ?? 0; }
  }
  vi.stubGlobal("PointerEvent", TestPointerEvent);
  const gradient = { addColorStop: vi.fn() };
  const context = new Proxy({ createRadialGradient: () => gradient, createLinearGradient: () => gradient }, {
    get(target, key) { return key in target ? target[key as keyof typeof target] : vi.fn(); },
    set() { return true; },
  });
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(context as unknown as CanvasRenderingContext2D);
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(1000);
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(800);
  vi.spyOn(Math, "random").mockReturnValue(.25);
  const listeners = new Map<string, () => void>();
  vi.stubGlobal("matchMedia", vi.fn((query: string) => ({ matches: query.includes("reduced-motion") && reduced,
    addEventListener: (_: string, callback: () => void) => listeners.set(query, callback), removeEventListener: vi.fn() })));
  const raf = vi.spyOn(window, "requestAnimationFrame").mockReturnValue(1);
  return { raf };
}

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("renders a still dish without scheduling animation under reduced motion", () => {
  const { raf } = setup(true);
  const { container } = render(<DishBackground obstacles={[]} />);
  expect(container.querySelector("canvas")).toHaveAttribute("aria-hidden", "true");
  expect(raf).not.toHaveBeenCalled();
});

it("releases a cancelled pointer so the next interaction can pick up a cell", () => {
  setup(true);
  const { container } = render(<DishBackground obstacles={[]} />);
  const canvas = container.querySelector("canvas")!;
  // With this seed, the initial body is at (280, 232). Cancellation must not strand the drag.
  fireEvent.pointerDown(canvas, { pointerId: 4, clientX: 280, clientY: 232, button: 0 });
  expect(canvas.style.cursor).toBe("grabbing");
  fireEvent.pointerCancel(canvas, { pointerId: 4 });
  expect(canvas.style.cursor).toBe("");
  fireEvent.pointerDown(canvas, { pointerId: 5, clientX: 280, clientY: 232, button: 0 });
  expect(canvas.style.cursor).toBe("grabbing");
  fireEvent.blur(window);
  expect(canvas.style.cursor).toBe("");
});
