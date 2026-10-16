/** Display contracts for the workbench views. Values here are presentation inputs, not scientific measurements. */

export type CultureState = "expanding" | "differentiating" | "frozen" | "grafted" | "draft";
export type Pathway = "smad" | "wnt" | "shh" | "fgf" | "notch" | "maturation" | "other";
export type ReagentKind = "molecule" | "protein" | "supplement";

export type Reagent = {
  id: string;
  name: string;
  /** Short label shown on the bar, e.g. CHIR. */
  short: string;
  pathway: Pathway;
  kind: ReagentKind;
  dose: string;
  /** First and last treatment day; null when the source document does not give it (never drawn as D0). */
  start: number | null;
  end: number | null;
  catalogId?: string;
  /** Fields the researcher still has to check before the version can be confirmed. */
  unconfirmed?: string[];
  /** Where the value came from in the uploaded document; preserved on every save. */
  sourceLocator?: string;
  /** The source's own wording for the timing when it is relative; shown, never turned into days. */
  timingText?: string;
  /** Values taken from a protocol the document cites, with where in that protocol. */
  recipeRefs?: { field: "dose_text" | "start_day" | "end_day"; locator: string }[];
  /** Server provenance of the dose and days as loaded; kept on save only for values left unchanged. */
  provenance?: { entries: NonNullable<import("./objects").ReagentDTO["field_provenance"]>; dose: string; start: number | null; end: number | null };
};

/** Five conditional fractions; null marks a level that could not be measured, never zero. */
export type ChainValue = number | null;
export type ChainValues = [ChainValue, ChainValue, ChainValue, ChainValue, ChainValue];

export type Sample = {
  day: number;
  /** Atlas node weights describing where the sample sits on the developmental tree. */
  position: Record<string, number>;
  chain: ChainValues;
  gestation: string;
  note: string;
  /** Up to 600 mapped cells in tree coordinates: [x, y, z, nodeIndex]. Absent only in examples, which draw an illustration instead. */
  mappedCells?: [number, number, number, number][];
  /** A real mapping result; absent for examples. */
  mapping?: MappingView;
  /** The registered sample and mapping this result belongs to; absent for examples. Several samples may share a day. */
  sampleId?: string;
  assessmentId?: string;
  /** The registered mapping analysis bound to this result, when the server names it. */
  analysisId?: string;
};

/** What a mapping result can honestly say: where cells landed and with which method, never a quality score it did not compute. */
export type MappingView = {
  method: string;
  /** True while the result is a candidate (not scientifically qualified). */
  candidate: boolean;
  /** Share of all cells per tree label, largest first. */
  branches: { label: string; share: number }[];
  /** Share of cells that have no position on the tree. */
  offTree: number;
  cells: number | null;
  /** Tree version the cell positions belong to; cells are drawn only on that exact tree. */
  treeVersion: string | null;
  reference: string | null;
  /** Readable limitations of the method. */
  limitations: string[];
  /** True when no chain level was computed. */
  chainMissing: boolean;
  /** Identity needed to read and check the stored marker expression; null when the result has none. */
  markers: { assessmentId: string; genes: string[]; features: string | null; normalization: string | null } | null;
};

/** Marker expression ready to colour the tree: one gene at a time, sample rows in `mappedCells` order. */
export type MarkerPanel = {
  genes: { gene: string; available: boolean; missingFrom: ("query" | "reference")[] }[];
  /** Per gene column: value for each mapped cell row (null = not measurable). */
  sample: (number | null)[][];
  /** Per tree cell index: values by gene column; tree cells absent here are not in the mapping reference. */
  reference: Map<number, (number | null)[]>;
  treeVersion: string; features: string; normalization: string;
};

export type Protocol = {
  id: string;
  name: string;
  version: number;
  state: CultureState;
  day: number;
  totalDays: number;
  today: string;
  lead?: string;
  graftWeeks?: number;
  reagents: Reagent[];
  samples: Sample[];
  /** Server identity of the protocol version shown; absent for examples. */
  source?: ProtocolSource;
  /** Present when this card is one run of a protocol. */
  run?: RunInfo;
  /** Every registered sample of the run, including those not yet mapped. */
  sampleRecords?: SampleRecord[];
  /** Scheduled operations of the version; a null day stays with its source step and is not scheduled. */
  operations?: { day: number | null; kind: string; note: string }[];
  /** Protocol-specific stage windows; absent means the default windows. */
  stages?: StageWindow[];
  /** Stage the server computed for a running culture; preferred over recomputing from the day. */
  stageIndex?: number | null;
};

/** One stage's inclusive day window. */
export type StageWindow = { index: 1 | 2 | 3 | 4; start: number; end: number };

export type RunState = "planned" | "expanding" | "differentiating" | "frozen" | "grafted" | "ended";
export type RunInfo = {
  id: string; revision: number; name: string; cellLine: string | null; startDate: string | null; state: RunState;
  graft: { date: string; host: string; site: string } | null; protocolVersionId: string;
  /** A retrospective run records an experiment already done (e.g. imported public data): no current day or reminders. */
  purpose?: "execution" | "retrospective";
};
export type MappingStatus = "none" | "pending" | "approved" | "running" | "done" | "failed";
/** Collected samples wait for sequencing; data arrives weeks later and is attached to the same sample. */
export type SampleStatus = "collected" | "data_attached" | "mapping" | "done" | "failed";
export type SampleRecord = { id: string; revision: number; day: number; assay: string; materialId: string | null; mapping: MappingStatus; status: SampleStatus;
  /** Readable reason standard mapping is not available for this sample's data yet. */
  unavailable?: string;
  /** Server code behind `unavailable`, which decides what the researcher can do next. */
  unavailableCode?: string;
  /** Whether the researcher has already declared the data; a declaration cannot be changed. */
  declared?: boolean;
  /** Collection date, used to suggest whether the sample was taken before or after grafting. */
  collectedOn?: string | null;
  /** The sample's current mapping attempt, which names its registered mapping analysis. */
  assessmentId?: string;
  /** The declaration as stored, so a later supplement (a capture batch) can be sent with the rest unchanged. */
  declaration?: import("./objects").MappingInputDTO };
/** `locations` lists the matrices found in an uploaded H5AD (X and layers/…); absent when the server does not report them. */
export type MaterialOption = { id: string; name: string; locations?: string[] };

/** The researcher's statement about attached data that mapping needs; nothing here is guessed from the file. */
export type MappingInput = {
  matrixLocation: string; sampleContext: "pre_graft" | "post_graft"; sourceFamily: string;
  /** Which capture (10x channel or library) each cell came from, so doublets are detected per capture; absent when not known. */
  capture?: { id: string } | { column: string };
};

export type StartRunInput = { name: string; cellLine: string; startDate: string; state: RunState };
export type SampleInput = { day: number; assay: "scRNA-seq" | "snRNA-seq"; collectedOn: string; materialId: string | null;
  /** Declaration sent with the data; null leaves the data attached and asks for it later. */
  mappingInput: MappingInput | null };

/** Server operations on runs and samples; present only when the workbench reads live objects. */
export type RunOps = {
  materials: MaterialOption[];
  uploadMaterial: (file: File) => Promise<MaterialOption>;
  start: (protocol: Protocol, input: StartRunInput) => Promise<string>;
  update: (run: RunInfo, patch: { state?: RunState; startDate?: string; graft?: RunInfo["graft"] }) => Promise<void>;
  addSample: (run: RunInfo, input: SampleInput) => Promise<{ notice?: string }>;
  /** Starts mapping again, or for the first time with a declaration given after the data was attached. */
  requestMapping: (sample: SampleRecord, input?: MappingInput) => Promise<{ notice?: string }>;
  /** Attaches sequencing data to a sample registered before it arrived. */
  attachData: (sample: SampleRecord, materialId: string, input: MappingInput | null) => Promise<{ notice?: string }>;
  /** Declares the capture batch of a sample whose data is already declared, which runs its standard analysis again. */
  addCapture: (sample: SampleRecord, capture: NonNullable<MappingInput["capture"]>) => Promise<{ notice?: string }>;
};

export type ProtocolSource = {
  protocolId: string; versionId: string; status: "draft" | "confirmed";
  protocolRevision: number; versionRevision: number; totalDaysSet: boolean;
  /** Whole-version items still to check; empty for manual and older versions. */
  review?: ReviewItem[];
  /** True when the version came from an uploaded document and has a source record. */
  hasSource?: boolean;
};

export type DraftPatch = { reagents?: Reagent[]; totalDays?: number; changeNote?: string; review?: ReviewItem[] };

/** Whole-version items an imported draft keeps for the researcher to check (contract §7.5). */
export type ReviewItem = "source_review" | "total_days" | "stages" | "operations";

/** One highlighted value the import took from the text; only literal presence is checked, not correctness. */
export type SourceQuote = { kind: "reagent" | "total" | "stage" | "operation"; text: string; name?: string };
/** Read-only record of where a version came from: the original segments, quoted values and open questions. */
export type SourceView = {
  segments: { id: string; label: string; location: string; text: string }[];
  quotes: SourceQuote[]; questions: string[]; compiled: boolean; needsInput: boolean;
};

/** Server operations on protocols; present only when the workbench reads live objects. */
export type ProtocolOps = {
  createManual: (name: string) => Promise<string>;
  importDocument: (file: File) => Promise<{ viewId: string; notice?: string }>;
  saveDraft: (protocol: Protocol, patch: DraftPatch) => Promise<void>;
  confirm: (protocol: Protocol) => Promise<void>;
  newVersion: (protocol: Protocol, patch?: DraftPatch) => Promise<string>;
  /** Source record of a version made from a document; null when the version has none. */
  formalization?: (protocol: Protocol) => Promise<SourceView | null>;
};

export type QueueItem = { id: string; title: string; context: string; tier: "exploratory" | "formal"; eta: string };

/** Developmental tree payload. Cells: [x, y, z, nodeIndex, gestationalWeek, pseudotime, isSingleCell]. */
export type DevTree = {
  subtypes: string[];
  nodes: [number, number, number][];
  edges: [number, number][];
  cells: [number, number, number, number, number, number, number][];
  source: string;
  synthetic?: boolean;
  /** Content hash of the tree; mapping results carry the version they were placed on. */
  version?: string;
};

export type Stage = { index: 0 | 1 | 2 | 3 | 4; tag: string; name: string };
