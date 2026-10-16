import { render, screen } from "@testing-library/react";
import { Incubator } from "../src/workbench/Incubator";
import { artFor, artForStage } from "../src/workbench/StageDish";
import type { Protocol } from "../src/workbench/types";

const culture = (id: string, patch: Partial<Protocol>): Protocol =>
  ({ id, name: id, version: 1, state: "differentiating", day: 12, totalDays: 28, today: "", reagents: [], samples: [], ...patch });

describe("culture dish artwork", () => {
  it("picks one illustration per culture state and stage", () => {
    expect([0, 1, 2, 3, 4].map(artForStage)).toEqual(["expansion", "stage-i-neural-induction", "stage-ii-floor-plate-induction",
      "stage-iii-floor-plate-progenitor", "stage-iv-neuronal-maturation"]);
    expect(artFor(culture("a", { state: "draft" }))).toBe("not-started");
    expect(artFor(culture("b", { state: "expanding", day: -2 }))).toBe("expansion");
    expect(artFor(culture("c", { day: 3 }))).toBe("stage-i-neural-induction");
    expect(artFor(culture("d", { day: 12, stageIndex: 2 }))).toBe("stage-ii-floor-plate-induction");
    expect(artFor(culture("e", { state: "frozen" }))).toBe("cryopreserved");
    expect(artFor(culture("f", { state: "grafted", graftWeeks: 6 }))).toBe("post-graft");
  });

  it("shows each card's dish and marks only growing cultures as live", () => {
    const { container } = render(<Incubator userName="wyx" queue={[]} onOpen={() => undefined}
      protocols={[culture("growing", { day: 20 }), culture("frozen", { state: "frozen" })]} />);
    expect(screen.getByRole("button", { name: /^打开growing/ })).toBeInTheDocument();
    const dishes = [...container.querySelectorAll<HTMLElement>(".wb-dish")];
    expect(dishes.map(d => d.dataset.art)).toEqual(["stage-iv-neuronal-maturation", "cryopreserved"]);
    expect(dishes.map(d => d.classList.contains("wb-dish--live"))).toEqual([true, false]);
    expect(dishes[0].querySelector("img")!.getAttribute("src")).toMatch(/illustrations\/culture-dishes\/stage-iv-neuronal-maturation\.svg$/);
    expect(dishes[0].getAttribute("aria-hidden")).toBe("true");
  });
});
