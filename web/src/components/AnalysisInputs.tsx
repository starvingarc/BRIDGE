import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type ReactNode,
} from "react";
import { ApiError, api } from "../api";
import type {
  AnalysisAssetInputContract,
  AnalysisAssetRegistration,
  AnalysisInputAsset,
  AnalysisInputObject,
  AnalysisInputRoleContract,
  AnalysisInputsResponse,
  AnalysisSelection,
  Session,
  ToolCapability,
  Upload,
} from "../types";

const OBJECT_FILE_LIMIT = 2 * 1024 * 1024;
const METADATA_FILE_LIMIT = 32 * 1024;
const SOURCE_LABELS: Record<AnalysisInputObject["source"], string> = {
  user_upload: "User-supplied",
  package_resource: "Package resource",
  system_resource: "Configured reference",
  tool_output: "Prior tool output",
};

type UploadChoice = { schemaRef: string; objectVersion: string };

type Props = {
  sessionId: string;
  uploads: Upload[];
  capabilities: ToolCapability[];
  disabled: boolean;
  onSession: (session: Session) => void;
  onError: (error: unknown) => void;
  children?: ReactNode;
};

const emptySelection = (toolId: string): AnalysisSelection => ({
  tool_id: toolId,
  mode_id: null,
  asset_ids: [],
  object_inputs: [],
  measurement_spec_ref: null,
});

const displayName = (value: string) => value.replaceAll("_", " ");

const sourceLabel = (object: AnalysisInputObject) =>
  object.source === "tool_output" && object.producer_tool_id
    ? `${SOURCE_LABELS[object.source]} · ${object.producer_tool_id}`
    : SOURCE_LABELS[object.source];

const publicError = (error: unknown) => {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return "The request could not be completed. Please try again.";
};

const normalizedSelection = (selection: AnalysisSelection) => ({
  ...selection,
  asset_ids: [...selection.asset_ids].sort(),
  object_inputs: [...selection.object_inputs].sort((left, right) =>
    left.role.localeCompare(right.role) || left.input_id.localeCompare(right.input_id),
  ),
});

const selectionsMatch = (
  draft: AnalysisSelection,
  saved: AnalysisSelection | undefined,
) => saved !== undefined
  && JSON.stringify(normalizedSelection(draft)) === JSON.stringify(normalizedSelection(saved));

const compatibleObjects = (
  objects: AnalysisInputObject[],
  role: AnalysisInputRoleContract,
) => objects.filter((object) =>
  role.schema_refs.includes(object.schema_ref)
  && (
    role.object_version_policy === "payload"
    || role.object_versions.includes(object.object_version)
  ));

function assetMatchesContract(
  asset: AnalysisInputAsset,
  contract: AnalysisAssetInputContract,
) {
  if (!asset.declaration) return false;
  const declaration = asset.declaration;
  return (
    (!contract.assays.length
      || (declaration.assay !== undefined && contract.assays.includes(declaration.assay)))
    && (!contract.input_levels.length
      || (
        declaration.input_level !== undefined
        && contract.input_levels.includes(declaration.input_level)
      ))
    && (!contract.matrix_semantics.length
      || (
        declaration.matrix_semantics !== undefined
        && contract.matrix_semantics.includes(declaration.matrix_semantics)
      ))
  );
}

async function parseObjectFile(
  file: File,
  limit: number,
  label: string,
): Promise<Record<string, unknown>> {
  if (file.size > limit) {
    throw new Error(`${label} exceeds the ${Math.round(limit / 1024)} KiB browser limit.`);
  }
  let value: unknown;
  try {
    value = JSON.parse(await file.text());
  } catch {
    throw new Error(`${label} must be valid JSON.`);
  }
  if (value === null || Array.isArray(value) || typeof value !== "object") {
    throw new Error(`${label} must contain one JSON object.`);
  }
  return value as Record<string, unknown>;
}

function uploadContract(
  role: AnalysisInputRoleContract,
  value: Record<string, unknown>,
  choice: UploadChoice,
) {
  const embeddedSchema = typeof value.schema_ref === "string" ? value.schema_ref : "";
  const schemaRef = choice.schemaRef
    || embeddedSchema
    || (role.schema_refs.length === 1 ? role.schema_refs[0] : "");
  if (!role.schema_refs.includes(schemaRef) || (embeddedSchema && embeddedSchema !== schemaRef)) {
    throw new Error("Choose the JSON object's compatible schema.");
  }

  if (role.object_version_policy === "fixed") {
    const objectVersion = choice.objectVersion
      || (role.object_versions.length === 1 ? role.object_versions[0] : "");
    if (!role.object_versions.includes(objectVersion)) {
      throw new Error("Choose the JSON object's compatible version.");
    }
    return { schemaRef, objectVersion };
  }

  const payloadVersion = ["object_version", "version", "graph_version"]
    .map((key) => value[key])
    .find((item): item is string => typeof item === "string" && item.trim().length > 0);
  const objectVersion = choice.objectVersion.trim() || payloadVersion || "";
  if (!objectVersion) {
    throw new Error("Declare the object's schema version in the file or version field.");
  }
  return { schemaRef, objectVersion };
}

function SelectField({
  label,
  value,
  options,
  emptyLabel = "Choose…",
  disabled,
  required,
  className = "",
  onChange,
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  emptyLabel?: string;
  disabled: boolean;
  required?: boolean;
  className?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className={className}>
      <span>{label}</span>
      <select
        value={value}
        disabled={disabled}
        required={required}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">{emptyLabel}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </label>
  );
}

function RolePicker({
  role, objects, selection, choice, disabled, uploading, onSelection, onChoice, onUpload,
}: {
  role: AnalysisInputRoleContract;
  objects: AnalysisInputObject[];
  selection: AnalysisSelection;
  choice: UploadChoice;
  disabled: boolean;
  uploading: boolean;
  onSelection: (role: AnalysisInputRoleContract, inputIds: string[]) => void;
  onChoice: (role: string, key: keyof UploadChoice, value: string) => void;
  onUpload: (event: ChangeEvent<HTMLInputElement>, role: AnalysisInputRoleContract) => void;
}) {
  const options = compatibleObjects(objects, role);
  const selected = selection.object_inputs
    .filter((item) => item.role === role.role)
    .map((item) => item.input_id);
  const usedElsewhere = new Set(selection.object_inputs
    .filter((item) => item.role !== role.role)
    .map((item) => item.input_id));
  const full = role.max_count !== null && selected.length >= role.max_count;
  return (
    <fieldset className="analysis-role" disabled={disabled}>
      <legend>
        {displayName(role.role)}
        <span>
          {role.min_count ? `required ${role.min_count}` : "optional"} ·{" "}
          {role.max_count === null ? "multiple" : `up to ${role.max_count}`}
        </span>
      </legend>
      <select
        aria-label={`${displayName(role.role)} object`}
        multiple={role.max_count !== 1}
        size={role.max_count === 1 ? undefined : Math.min(4, Math.max(2, options.length))}
        value={role.max_count === 1 ? selected[0] ?? "" : selected}
        onChange={(event) => {
          const ids = Array.from(event.currentTarget.selectedOptions, (option) => option.value);
          onSelection(role, role.max_count === null ? ids : ids.slice(0, role.max_count));
        }}
      >
        {role.max_count === 1 ? <option value="">No object selected</option> : null}
        {options.map((object) => (
          <option
            key={object.id}
            value={object.id}
            disabled={usedElsewhere.has(object.id) || (full && !selected.includes(object.id))}
          >
            {object.label} · {sourceLabel(object)}
          </option>
        ))}
      </select>
      {!options.length ? (
        <small className="analysis-input-hint">No compatible registered objects.</small>
      ) : null}
      <div className="analysis-upload-contract">
        {role.schema_refs.length > 1 ? (
          <SelectField
            label="JSON schema"
            value={choice.schemaRef}
            disabled={disabled}
            onChange={(value) => onChoice(role.role, "schemaRef", value)}
            options={role.schema_refs.map((value) => ({ value, label: value }))}
          />
        ) : null}
        {role.object_version_policy === "fixed" && role.object_versions.length > 1 ? (
          <SelectField
            label="Object version"
            value={choice.objectVersion}
            disabled={disabled}
            onChange={(value) => onChoice(role.role, "objectVersion", value)}
            options={role.object_versions.map((value) => ({ value, label: value }))}
          />
        ) : null}
        {role.object_version_policy === "payload" ? (
          <label>
            <span>Object version (if not declared in the file)</span>
            <input
              value={choice.objectVersion}
              disabled={disabled}
              maxLength={80}
              onChange={(event) => onChoice(role.role, "objectVersion", event.target.value)}
            />
          </label>
        ) : null}
      </div>
      <label className="analysis-file-button">
        <span>{uploading ? "Registering…" : "Register scientific JSON"}</span>
        <input
          className="sr-only"
          type="file"
          accept=".json,application/json"
          disabled={disabled || role.max_count === 0}
          onChange={(event) => void onUpload(event, role)}
          aria-label={`Register JSON for ${displayName(role.role)}`}
        />
      </label>
      <small>One JSON object, up to 2 MiB. The server verifies its schema and version.</small>
    </fieldset>
  );
}

export function AnalysisInputs({
  sessionId,
  uploads,
  capabilities,
  disabled,
  onSession,
  onError,
  children,
}: Props) {
  const activeSession = useRef(sessionId);
  activeSession.current = sessionId;
  const mounted = useRef(true);
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const assetForm = useRef<HTMLFormElement>(null);
  const [registry, setRegistry] = useState<{
    sessionId: string;
    data: AnalysisInputsResponse | null;
    loading: boolean;
    error: string | null;
  }>({ sessionId, data: null, loading: false, error: null });
  const [selectedToolId, setSelectedToolId] = useState("");
  const [drafts, setDrafts] = useState<Record<string, AnalysisSelection>>({});
  const [metadata, setMetadata] = useState<{
    value: Record<string, unknown>;
    name: string | null;
  }>({ value: {}, name: null });
  const [uploadChoices, setUploadChoices] = useState<Record<string, UploadChoice>>({});
  const [mutation, setMutation] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      generation.current += 1;
      controller.current?.abort();
    };
  }, []);

  const data = registry.sessionId === sessionId ? registry.data : null;
  const loading = registry.sessionId === sessionId && registry.loading;
  const registryError = registry.sessionId === sessionId ? registry.error : null;
  const tool = data?.tools.find((item) => item.tool_id === selectedToolId);
  const draft = selectedToolId ? drafts[selectedToolId] ?? emptySelection(selectedToolId) : null;
  const saved = selectedToolId ? data?.selections[selectedToolId] : undefined;
  const mode = tool && draft?.mode_id
    ? tool.input_contract.object_input_modes.find((item) => item.mode_id === draft.mode_id)
    : undefined;
  const assetContract = tool
    ? mode?.asset_input ?? tool.input_contract.asset_input
    : null;
  const assets = data && assetContract
    ? data.assets.filter((asset) => assetMatchesContract(asset, assetContract))
    : [];
  const panelDisabled = disabled || mutation !== null;
  const dirty = draft ? !selectionsMatch(draft, saved) : false;
  const capability = capabilities.find((item) => item.tool_id === selectedToolId);
  const alive = (id: string) => mounted.current && activeSession.current === id;

  const setDraft = (next: AnalysisSelection) => {
    setDrafts((current) => ({ ...current, [next.tool_id]: next }));
    setNotice(null);
  };

  const updateUploadChoice = (role: string, key: keyof UploadChoice, value: string) =>
    setUploadChoices((current) => {
      const choice = current[role] ?? { schemaRef: "", objectVersion: "" };
      return { ...current, [role]: { ...choice, [key]: value } };
    });

  const reportError = (error: unknown) => {
    if ((error as { name?: string }).name === "AbortError") return;
    setLocalError(publicError(error));
    if (error instanceof ApiError) onError(error);
  };

  const loadRegistry = async () => {
    const requestGeneration = ++generation.current;
    controller.current?.abort();
    const requestController = new AbortController();
    controller.current = requestController;
    setRegistry((current) => ({
      sessionId,
      data: current.sessionId === sessionId ? current.data : null,
      loading: true,
      error: null,
    }));
    try {
      const next = await api.getAnalysisInputs(sessionId, requestController.signal);
      if (!alive(sessionId) || requestGeneration !== generation.current) return;
      setRegistry({ sessionId, data: next, loading: false, error: null });
      setDrafts((current) => ({
        ...Object.fromEntries(
          Object.entries(next.selections).filter(([toolId]) => !current[toolId]),
        ),
        ...current,
      }));
    } catch (error) {
      if (
        !alive(sessionId)
        || requestGeneration !== generation.current
        || (error as { name?: string }).name === "AbortError"
      ) return;
      setRegistry((current) => ({
        sessionId,
        data: current.sessionId === sessionId ? current.data : null,
        loading: false,
        error: publicError(error),
      }));
      onError(error);
    }
  };

  const runMutation = async (
    kind: string,
    request: () => Promise<Session>,
    after: (() => void) | undefined,
    message: string | ((session: Session) => string),
  ) => {
    if (panelDisabled) return;
    const operationSession = sessionId;
    setMutation(kind);
    setLocalError(null);
    setNotice(null);
    try {
      const next = await request();
      if (!alive(operationSession)) return;
      onSession(next);
      after?.();
      setNotice(typeof message === "function" ? message(next) : message);
      await loadRegistry();
    } catch (error) {
      if (alive(operationSession)) reportError(error);
    } finally {
      if (alive(operationSession)) setMutation(null);
    }
  };

  const selectTool = (toolId: string) => {
    setSelectedToolId(toolId);
    assetForm.current?.reset();
    setMetadata({ value: {}, name: null });
    setUploadChoices({});
    setLocalError(null);
    setNotice(null);
    if (!toolId || !data) return;
    setDrafts((current) => current[toolId]
      ? current
      : { ...current, [toolId]: data.selections[toolId] ?? emptySelection(toolId) });
  };

  const changeMode = (modeId: string) => {
    if (!draft || !tool || !data) return;
    const nextMode = tool.input_contract.object_input_modes.find(
      (item) => item.mode_id === modeId,
    );
    const roles = nextMode?.roles ?? [];
    const objectInputs = draft.object_inputs.filter((input) => {
      const role = roles.find((item) => item.role === input.role);
      const object = data.objects.find((item) => item.id === input.input_id);
      return role && object && compatibleObjects([object], role).length;
    });
    const nextAssetContract = nextMode?.asset_input ?? tool.input_contract.asset_input;
    const assetIds = nextAssetContract
      ? draft.asset_ids.filter((id) => {
          const asset = data.assets.find((item) => item.id === id);
          return asset && assetMatchesContract(asset, nextAssetContract);
        })
      : [];
    setDraft({
      ...draft,
      mode_id: modeId || null,
      object_inputs: objectInputs,
      asset_ids: assetIds,
    });
    assetForm.current?.reset();
    setMetadata({ value: {}, name: null });
    setUploadChoices({});
  };

  const changeRole = (role: AnalysisInputRoleContract, inputIds: string[]) => {
    if (!draft) return;
    setDraft({
      ...draft,
      object_inputs: [
        ...draft.object_inputs.filter((item) => item.role !== role.role),
        ...inputIds.map((input_id) => ({ role: role.role, input_id })),
      ],
    });
  };

  const changeAssets = (assetIds: string[]) => {
    if (draft) setDraft({ ...draft, asset_ids: assetIds });
  };

  const saveSelection = () => {
    if (!draft) return;
    void runMutation(
      "save",
      () => api.saveAnalysisInputs(sessionId, draft),
      () => setRegistry((current) => current.sessionId === sessionId && current.data
        ? {
            ...current,
            data: {
              ...current.data,
              selections: { ...current.data.selections, [draft.tool_id]: draft },
            },
          }
        : current),
      "Selection saved. Prepare plan remains a separate action.",
    );
  };

  const preparePlan = () => {
    if (!draft || dirty) return;
    void runMutation(
      "prepare",
      () => api.prepareAnalysis(sessionId, draft.tool_id),
      undefined,
      (next) => next.status === "awaiting_approval" && next.plan?.status === "proposed"
        ? "Plan prepared. It has not been approved or run."
        : `Plan not prepared: ${displayName(
            next.error ?? "required inputs remain unresolved",
          ).replaceAll(":", " ")}.`,
    );
  };

  const uploadObject = (
    event: ChangeEvent<HTMLInputElement>,
    role: AnalysisInputRoleContract,
  ) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !draft) return;
    void runMutation(
      `object:${role.role}`,
      async () => {
        const value = await parseObjectFile(file, OBJECT_FILE_LIMIT, "Scientific JSON file");
        const contract = uploadContract(
          role,
          value,
          uploadChoices[role.role] ?? { schemaRef: "", objectVersion: "" },
        );
        return api.uploadAnalysisObject(sessionId, {
          toolId: draft.tool_id,
          modeId: draft.mode_id,
          role: role.role,
          schemaRef: contract.schemaRef,
          objectVersion: contract.objectVersion,
          file,
        });
      },
      undefined,
      `${file.name} registered. Select its opaque object entry, then save.`,
    );
  };

  const loadMetadata = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      const value = await parseObjectFile(file, METADATA_FILE_LIMIT, "Metadata JSON file");
      setMetadata({ value, name: file.name });
      setLocalError(null);
    } catch (error) {
      setLocalError(publicError(error));
    }
  };

  const registerAsset = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!assetContract) return;
    const form = new FormData(event.currentTarget);
    const field = (name: string) => String(form.get(name) ?? "");
    const registration: AnalysisAssetRegistration = {
      upload_id: field("upload_id"),
      assay: field("assay"),
      matrix_location: field("matrix_location"),
      matrix_semantics: field("matrix_semantics"),
      input_level: field("input_level"),
      metadata: metadata.value,
    };
    if (Object.values(registration).some((value) => value === "")) {
      setLocalError("Choose an H5AD upload and make every asset declaration explicitly.");
      return;
    }
    void runMutation(
      "asset",
      () => api.registerAnalysisAsset(sessionId, registration),
      () => {
        assetForm.current?.reset();
        setMetadata({ value: {}, name: null });
      },
      "H5AD declaration registered. Select the registered asset, then save.",
    );
  };

  const missingReasons: string[] = [];
  if (tool && draft) {
    if (tool.input_contract.object_input_modes.length && !mode) {
      missingReasons.push("Select an input mode.");
    }
    for (const role of mode?.roles ?? []) {
      const count = draft.object_inputs.filter((item) => item.role === role.role).length;
      const missing = role.min_count - count;
      if (missing > 0) {
        missingReasons.push(
          `${displayName(role.role)} needs ${missing} more input${missing === 1 ? "" : "s"}.`,
        );
      }
    }
    if (assetContract && draft.asset_ids.length < assetContract.min_count) {
      const missing = assetContract.min_count - draft.asset_ids.length;
      missingReasons.push(
        `Input assets need ${missing} more selection${missing === 1 ? "" : "s"}.`,
      );
    }
    if (
      tool.input_contract.measurement_spec_ref_policy === "required"
      && !draft.measurement_spec_ref
    ) {
      missingReasons.push("A measurement specification is required.");
    }
  }

  const assetSelects = assetContract ? [
    { name: "assay", label: "Assay", values: assetContract.assays },
    { name: "matrix_semantics", label: "Matrix semantics", values: assetContract.matrix_semantics },
    { name: "input_level", label: "Input level", values: assetContract.input_levels },
  ] : [];

  return (
    <details
      className="analysis-context"
      onToggle={(event) => {
        if (event.currentTarget.open) void loadRegistry();
      }}
    >
      <summary>Analysis inputs</summary>
      <div className="analysis-inputs">
        {children ? <div className="analysis-inputs-existing">{children}</div> : null}
        {capabilities.length ? (
          <ul className="capability-list" aria-label="Tool-chain status">
            {capabilities.map((item) => (
              <li key={item.tool_id}>
                <span><strong>{item.tool_id}</strong> {item.label}</span>
                <span className={`capability-state capability-state--${item.state}`}>
                  {displayName(item.state)}
                </span>
                {item.reason_codes.length ? (
                  <small>{item.reason_codes.map(displayName).join(" · ")}</small>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
        <div className="analysis-inputs-heading">
          <div>
            <strong>Tool-chain selection</strong>
            <small>Save inputs before preparing a proposal.</small>
          </div>
          {loading ? <span role="status">Refreshing…</span> : null}
        </div>
        {registryError ? (
          <div className="analysis-input-error" role="alert">
            <span>{registryError}</span>
            <button type="button" onClick={() => void loadRegistry()} disabled={panelDisabled}>
              Retry
            </button>
          </div>
        ) : null}

        {data ? (
          <>
            <SelectField
              className="analysis-input-field"
              label="Analysis tool"
              value={selectedToolId}
              emptyLabel="Choose a tool…"
              disabled={panelDisabled}
              onChange={selectTool}
              options={data.tools.map((item) => ({
                value: item.tool_id,
                label: `${item.tool_id} · ${item.label}`,
              }))}
            />
            {tool && draft ? (
              <div className="analysis-selection">
                {tool.input_contract.object_input_modes.length ? (
                  <SelectField
                    className="analysis-input-field"
                    label="Input mode"
                    value={draft.mode_id ?? ""}
                    emptyLabel="Choose a mode…"
                    disabled={panelDisabled}
                    onChange={changeMode}
                    options={tool.input_contract.object_input_modes.map((item) => ({
                      value: item.mode_id,
                      label: displayName(item.mode_id),
                    }))}
                  />
                ) : null}
                <p className="selected-mode">
                  Exact selected mode: <code>{draft.mode_id ?? "none"}</code>
                </p>

                {(mode?.roles ?? []).map((role) => (
                  <RolePicker
                    key={role.role}
                    role={role}
                    objects={data.objects}
                    selection={draft}
                    choice={uploadChoices[role.role] ?? { schemaRef: "", objectVersion: "" }}
                    disabled={panelDisabled}
                    uploading={mutation === `object:${role.role}`}
                    onSelection={changeRole}
                    onChoice={updateUploadChoice}
                    onUpload={uploadObject}
                  />
                ))}

                {assetContract ? (
                  <section className="analysis-assets" aria-labelledby="analysis-assets-title">
                    <div className="analysis-subheading">
                      <strong id="analysis-assets-title">Registered H5AD assets</strong>
                      <small>
                        {assetContract.min_count
                          ? `required ${assetContract.min_count}`
                          : "optional"}
                        {" · "}
                        {assetContract.max_count === null
                          ? "multiple"
                          : `up to ${assetContract.max_count}`}
                      </small>
                    </div>
                    <select
                      aria-label="Registered H5AD asset"
                      multiple={assetContract.max_count !== 1}
                      size={assetContract.max_count === 1 ? undefined : 3}
                      value={assetContract.max_count === 1 ? draft.asset_ids[0] ?? "" : draft.asset_ids}
                      disabled={panelDisabled}
                      onChange={(event) => {
                        const ids = Array.from(
                          event.currentTarget.selectedOptions,
                          (option) => option.value,
                        );
                        changeAssets(assetContract.max_count === null
                          ? ids
                          : ids.slice(0, assetContract.max_count));
                      }}
                    >
                      {assetContract.max_count === 1
                        ? <option value="">No asset selected</option>
                        : null}
                      {assets.map((asset) => (
                        <option key={asset.id} value={asset.id}>{asset.label}</option>
                      ))}
                    </select>
                    {!assets.length ? (
                      <small className="analysis-input-hint">
                        No compatible registered H5AD assets.
                      </small>
                    ) : null}

                    <form ref={assetForm} className="asset-registration" onSubmit={registerAsset}>
                      <strong>Register an uploaded H5AD</strong>
                      <label>
                        <span>Uploaded H5AD</span>
                        <select name="upload_id" defaultValue="" disabled={panelDisabled} required>
                          <option value="">Choose an upload…</option>
                          {uploads.filter((upload) => upload.kind === "h5ad").map((upload) => (
                            <option key={upload.id} value={upload.id}>{upload.name}</option>
                          ))}
                        </select>
                      </label>
                      <div className="asset-declaration-grid">
                        {assetSelects.map((field) => (
                          <label key={field.name}>
                            <span>{field.label}</span>
                            <select name={field.name} defaultValue="" disabled={panelDisabled} required>
                              <option value="">Choose…</option>
                              {field.values.map((value) => (
                                <option key={value} value={value}>{displayName(value)}</option>
                              ))}
                            </select>
                          </label>
                        ))}
                        <label>
                          <span>Matrix location</span>
                          <input
                            name="matrix_location"
                            disabled={panelDisabled}
                            pattern={"X|layers/[A-Za-z0-9_.\\-]{1,80}"}
                            placeholder="X or layers/counts"
                            title="Use X or a named H5AD layer such as layers/counts."
                            required
                          />
                        </label>
                      </div>
                      <label className="analysis-file-button">
                        <span>Advanced metadata JSON</span>
                        <input
                          className="sr-only"
                          type="file"
                          accept=".json,application/json"
                          disabled={panelDisabled}
                          onChange={(event) => void loadMetadata(event)}
                          aria-label="Choose advanced metadata JSON"
                        />
                      </label>
                      <small>
                        {metadata.name
                          ? `${metadata.name} loaded.`
                          : "Optional object file, up to 32 KiB. No biological facts are inferred."}
                      </small>
                      {assetContract.required_metadata_keys.length ? (
                        <small>
                          Contract-required metadata:{" "}
                          {assetContract.required_metadata_keys.join(", ")}.
                        </small>
                      ) : null}
                      <button type="submit" disabled={panelDisabled || !uploads.length}>
                        {mutation === "asset" ? "Registering…" : "Register declaration"}
                      </button>
                    </form>
                  </section>
                ) : null}

                {tool.input_contract.measurement_spec_ref_policy !== "forbidden" ? (
                  <SelectField
                    className="analysis-input-field"
                    label={`Measurement specification (${tool.input_contract.measurement_spec_ref_policy})`}
                    value={draft.measurement_spec_ref ?? ""}
                    emptyLabel="No measurement specification"
                    disabled={panelDisabled}
                    onChange={(value) =>
                      setDraft({ ...draft, measurement_spec_ref: value || null })}
                    options={data.measurement_specs.map((item) => ({
                      value: item.id,
                      label: item.label,
                    }))}
                  />
                ) : null}

                {missingReasons.length || capability?.reason_codes.length ? (
                  <div className="analysis-missing">
                    <strong>Missing or unresolved inputs</strong>
                    <ul>
                      {missingReasons.map((reason) => <li key={reason}>{reason}</li>)}
                      {capability?.reason_codes.map((reason) => (
                        <li key={reason}>Server: {displayName(reason)}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <p className="analysis-input-caveat">
                  Listed options are contract-compatible, not proof of scientific validity or full-chain success.
                </p>
                {localError ? (
                  <p className="analysis-input-error" role="alert">{localError}</p>
                ) : null}
                {notice ? <p className="analysis-input-notice" role="status">{notice}</p> : null}
                <div className="analysis-input-actions">
                  <button
                    type="button"
                    onClick={saveSelection}
                    disabled={panelDisabled || !dirty}
                  >
                    {mutation === "save" ? "Saving…" : "Save selection"}
                  </button>
                  <button
                    type="button"
                    className="analysis-prepare-button"
                    onClick={preparePlan}
                    disabled={panelDisabled || dirty}
                  >
                    {mutation === "prepare" ? "Preparing…" : "Prepare plan"}
                  </button>
                </div>
                {dirty ? (
                  <small className="analysis-input-hint">
                    Save this new or changed selection before preparing a plan.
                  </small>
                ) : null}
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </details>
  );
}
