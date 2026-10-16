/** Reading a quick atlas mapping result, and the declaration researchers give before mapping (contract §7.6). */
import type { AssessmentDTO, MappingInputDTO, MarkerExpressionDTO } from "./objects";
import type { MappingInput, MappingView, MarkerPanel, RunInfo } from "./types";

const CLASS: Record<string, string> = { RG: "放射胶质", Nb: "神经母细胞" };
const REGION: Record<string, string> = { mFP: "底板" };
const NEURON: Record<string, string> = { DA: "多巴胺能神经元", Glut: "谷氨酸能神经元", GABA: "GABA 能神经元", Glut_GABA: "谷氨酸/GABA 能神经元" };

/**
 * Researcher-facing name of an atlas label. Only the floor plate is named in words; other regional codes
 * (mBIP, mBMP …) stay as written because their roles are still under review, so the code is never hidden.
 */
export function cellTypeName(code: string): string {
  if (code === "Progenitor_root") return "早期祖细胞";
  const progenitor = /^(RG|Nb)_(.+)$/.exec(code);
  if (progenitor) return `${REGION[progenitor[2]] ?? progenitor[2]} ${CLASS[progenitor[1]]}`.trim();
  const neuron = /^Neuron_(.+)$/.exec(code);
  if (neuron) {
    if (NEURON[neuron[1]]) return NEURON[neuron[1]];
    const sub = /^(Glut|GABA)_([A-Z])$/.exec(neuron[1]);
    if (sub) return `${NEURON[sub[1]]} ${sub[2]}`;
  }
  return code;
}

const LIMITATIONS: Record<string, string> = {
  closed_set_label_transfer_not_ood_detection: "只在参考已有的细胞类型里找最像的，发现不了参考里没有的细胞。",
  gestation_not_donor_holdout_validated: "孕周是最近邻参考细胞的分布，没有校准成发育年龄。",
  tree_positions_are_reference_display_neighbors: "树上的点画在最像的参考细胞的位置，不是重新计算的发育轨迹。",
  chain_not_computed: "分化链各级指标还没有计算。",
};
export const limitationText = (code: string) => LIMITATIONS[code] ?? code;

/** The view a mapping result supports; every share keeps all cells as its denominator. */
export function mappingView(a: AssessmentDTO): MappingView {
  const branches = Object.entries(a.tree_position).filter(([, share]) => share > 0)
    .map(([label, share]) => ({ label, share })).sort((x, y) => y.share - x.share);
  const placed = branches.reduce((sum, b) => sum + b.share, 0);
  const offTree = a.n_cells ? (a.tree_unavailable_cells ?? 0) / a.n_cells : Math.max(0, 1 - placed);
  return {
    method: a.method_label ?? "图谱映射", candidate: a.scientific_status === "candidate", branches, offTree,
    cells: a.n_cells ?? null, treeVersion: a.versions.tree ?? null, reference: a.versions.reference ?? null,
    limitations: (a.limitations ?? []).map(limitationText), chainMissing: a.chain.every(level => level.value === null),
    markers: a.marker_expression?.status === "available"
      ? { assessmentId: a.id, genes: a.marker_expression.genes ?? [], features: a.versions.features ?? null, normalization: a.normalization ?? null } : null,
  };
}

/** Reads a stored panel into the view shape; rows stay in the server's order. */
export function markerPanel(dto: MarkerExpressionDTO): MarkerPanel {
  const sample = dto.genes.map((_, column) => dto.sample.values.map(row => row[column] ?? null));
  const reference = new Map(dto.reference.tree_cell_indices.map((index, row) => [index, dto.reference.values[row]] as const));
  return {
    genes: dto.genes.map(gene => {
      const status = dto.gene_status.find(g => g.gene === gene);
      return { gene, available: status?.status === "available", missingFrom: status?.missing_from ?? [] };
    }),
    sample, reference, treeVersion: dto.tree_version, features: dto.feature_set_sha256, normalization: dto.normalization,
  };
}

/**
 * Why a panel may not colour this tree, or null when it may: the tree, the mapping result and the panel must name the
 * same tree, and the panel must come from the same shared genes and normalisation as the result.
 */
export function markerMismatch(panel: MarkerPanel, view: MappingView, treeVersion: string | undefined): string | null {
  if (!treeVersion || panel.treeVersion !== treeVersion || view.treeVersion !== treeVersion) return "表达数据和当前发育树不是同一版本，不着色。";
  if (view.markers?.features && panel.features !== view.markers.features) return "表达数据和这次映射用的基因集合不一致，不着色。";
  if (view.markers?.normalization && panel.normalization !== view.markers.normalization) return "表达数据的归一化方式和这次映射不一致，不着色。";
  return null;
}

/** Upper end of the colour scale: the 99th percentile of measured values, so a few outliers do not wash out the rest. */
export function expressionCeiling(values: Iterable<number | null>): number {
  const list = [...values].filter((v): v is number => v !== null && Number.isFinite(v)).sort((a, b) => a - b);
  if (!list.length) return 0;
  return list[Math.min(list.length - 1, Math.floor(list.length * 0.99))] || list[list.length - 1];
}

/** One factual sentence for the pin on the tree. */
export function mappingNote(view: MappingView): string {
  const top = view.branches[0];
  return top ? `落在${cellTypeName(top.label)}最多（${Math.round(top.share * 100)}%）` : "细胞没有落在树上";
}

/** Branches for the summary bars: the largest few, the rest grouped, and cells off the tree last. */
export function branchBars(view: MappingView, shown = 3): { key: string; name: string; code?: string; share: number }[] {
  const head = view.branches.slice(0, shown), rest = view.branches.slice(shown);
  const restShare = rest.reduce((sum, b) => sum + b.share, 0);
  return [
    ...head.map(b => ({ key: b.label, name: cellTypeName(b.label), code: b.label, share: b.share })),
    ...(rest.length ? [{ key: "rest", name: `其他 ${rest.length} 根枝`, share: restShare }] : []),
    ...(view.offTree > 0 ? [{ key: "off", name: "未落在树上", share: view.offTree }] : []),
  ];
}

/** Display name for a matrix inside an H5AD. */
export const matrixName = (location: string) =>
  location === "X" ? "主矩阵 X" : location.startsWith("layers/") ? `${location.slice(7)} 层` : location;

const FAMILY = /^[A-Za-z0-9][A-Za-z0-9_.:-]*$/;
export const validSourceFamily = (value: string) => value.length <= 160 && FAMILY.test(value);

/** Suggested source group: the run's cell line in the allowed spelling, or the run itself. */
export function suggestedSourceFamily(run: RunInfo): string {
  const line = (run.cellLine ?? "").trim().replace(/\s+/g, "-").replace(/[^A-Za-z0-9_.:-]/g, "").replace(/^[^A-Za-z0-9]+/, "");
  return line && validSourceFamily(line) ? line : `run-${run.id.slice(0, 8)}`;
}

/** Collected on or after the graft date means a post-graft sample; otherwise pre-graft. */
export function suggestedContext(run: RunInfo, collectedOn: string | null | undefined): MappingInput["sampleContext"] {
  return run.graft && collectedOn && collectedOn >= run.graft.date ? "post_graft" : "pre_graft";
}

export const mappingInputDTO = (input: MappingInput): MappingInputDTO => ({
  matrix_location: input.matrixLocation, matrix_semantics: "raw_counts", sample_context: input.sampleContext, source_family_id: input.sourceFamily,
  ...(input.capture && "id" in input.capture ? { capture_id: input.capture.id } : input.capture ? { capture_id_column: input.capture.column } : {}),
});
