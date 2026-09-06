import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { AnalysisInputs } from "../src/components/AnalysisInputs";
import type { AnalysisInputsResponse, Session } from "../src/types";

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const session = (id = "session-a"): Session => ({
  id,
  title: id,
  updated_at: "2026-09-07T00:00:00Z",
  status: "idle",
  messages: [],
  uploads: [],
  plan: null,
  artifacts: [],
  error: null,
});

const role = {
  role: "product_case",
  schema_refs: ["bridge://schemas/product-case/v0.1"],
  object_version_policy: "fixed" as const,
  object_versions: ["0.1.0"],
  min_count: 1,
  max_count: 1,
};

const registry = (toolId = "P0-06", label = "Program response"): AnalysisInputsResponse => ({
  tools: [
    {
      tool_id: toolId,
      label,
      input_contract: {
        tool_id: toolId,
        request_schema_ref: "bridge://schemas/tool-request/v0.2",
        asset_input: null,
        measurement_spec_ref_policy: "optional",
        parameters_allowed: false,
        random_seed_policy: "fixed_zero",
        object_input_modes: [
          {
            mode_id: "supplied_evidence",
            roles: [role],
            asset_input: null,
          },
        ],
      },
    },
  ],
  objects: [
    {
      id: "user-object",
      label: "Supplied product case",
      schema_ref: "bridge://schemas/product-case/v0.1",
      object_version: "0.1.0",
      source: "user_upload",
      producer_tool_id: null,
    },
    {
      id: "package-object",
      label: "Package product case",
      schema_ref: "bridge://schemas/product-case/v0.1",
      object_version: "0.1.0",
      source: "package_resource",
      producer_tool_id: null,
    },
    {
      id: "configured-object",
      label: "Configured product case",
      schema_ref: "bridge://schemas/product-case/v0.1",
      object_version: "0.1.0",
      source: "system_resource",
      producer_tool_id: null,
    },
    {
      id: "prior-object",
      label: "Prior product case",
      schema_ref: "bridge://schemas/product-case/v0.1",
      object_version: "0.1.0",
      source: "tool_output",
      producer_tool_id: "P0-05",
    },
    {
      id: "wrong-schema",
      label: "Wrong schema",
      schema_ref: "bridge://schemas/program-spec/v0.1",
      object_version: "0.1.0",
      source: "package_resource",
      producer_tool_id: null,
    },
  ],
  assets: [],
  selections: {},
  measurement_specs: [{ id: "measurement-1", label: "Measurement one" }],
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

const props = (overrides: Partial<React.ComponentProps<typeof AnalysisInputs>> = {}) => ({
  sessionId: "session-a",
  uploads: [],
  capabilities: [],
  disabled: false,
  onSession: vi.fn(),
  onError: vi.fn(),
  ...overrides,
});

async function openPanel(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByText("Analysis inputs"));
}

async function chooseContract(user: ReturnType<typeof userEvent.setup>) {
  await user.selectOptions(await screen.findByLabelText("Analysis tool"), "P0-06");
  await user.selectOptions(screen.getByLabelText("Input mode"), "supplied_evidence");
}

describe("AnalysisInputs", () => {
  it("lazy-loads registry-driven modes and shows only compatible object options with friendly ownership", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(registry()));
    const user = userEvent.setup();
    render(
      <StrictMode>
        <AnalysisInputs {...props()} />
      </StrictMode>,
    );

    expect(fetchMock).not.toHaveBeenCalled();
    await openPanel(user);
    expect(await screen.findByRole("option", { name: "P0-06 · Program response" })).toBeInTheDocument();

    await chooseContract(user);

    expect(screen.getByText("Exact selected mode:")).toHaveTextContent("supplied_evidence");
    expect(screen.getByRole("option", { name: "Supplied product case · User-supplied" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Package product case · Package resource" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Configured product case · Configured reference" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Prior product case · Prior tool output · P0-05" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Wrong schema/ })).not.toBeInTheDocument();
    expect(screen.getByText(/contract-compatible, not proof of scientific validity/)).toBeInTheDocument();
  });

  it.each([
    ["P0-03", "Target identity and regional fidelity"],
    ["P0-04", "Developmental compatibility"],
  ])("inherits the top-level optional normalized-expression asset contract for %s", async (
    toolId,
    label,
  ) => {
    const response = registry(toolId, label);
    const inheritedAssetContract = {
      min_count: 0,
      max_count: 1,
      formats: ["h5ad"],
      assays: ["scRNA-seq", "snRNA-seq"],
      input_levels: ["analysis_ready"],
      matrix_semantics: ["normalized_expression"],
      required_metadata_keys: ["data_view_id", "parent_asset_sha256"],
    };
    response.tools[0].input_contract.asset_input = inheritedAssetContract;
    response.tools[0].input_contract.object_input_modes[0] = {
      ...response.tools[0].input_contract.object_input_modes[0],
      mode_id: "default",
      asset_input: null,
    };
    response.assets = [{
      id: "normalized-asset",
      label: "Normalized product H5AD",
      declaration: {
        upload_id: "upload-1",
        assay: "scRNA-seq",
        matrix_location: "X",
        matrix_semantics: "normalized_expression",
        input_level: "analysis_ready",
      },
    }];
    response.selections[toolId] = {
      tool_id: toolId,
      mode_id: null,
      asset_ids: ["normalized-asset"],
      object_inputs: [],
      measurement_spec_ref: null,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(response));
    const user = userEvent.setup();
    render(
      <AnalysisInputs
        {...props({
          uploads: [{ id: "upload-1", name: "case.h5ad", kind: "h5ad", size: 12 }],
        })}
      />,
    );

    await openPanel(user);
    await user.selectOptions(screen.getByLabelText("Analysis tool"), toolId);
    await user.selectOptions(screen.getByLabelText("Input mode"), "default");

    expect(screen.getByLabelText("Registered H5AD asset")).toHaveValue("normalized-asset");
    expect(screen.getByRole("option", { name: "Normalized product H5AD" })).toBeInTheDocument();
    expect(screen.getByLabelText("Uploaded H5AD")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "normalized expression" })).toBeInTheDocument();
  });

  it("uses an explicit mode asset override instead of the top-level contract", async () => {
    const response = registry("P0-03", "Target identity and regional fidelity");
    response.tools[0].input_contract.asset_input = {
      min_count: 0,
      max_count: 1,
      formats: ["h5ad"],
      assays: ["scRNA-seq"],
      input_levels: ["analysis_ready"],
      matrix_semantics: ["normalized_expression"],
      required_metadata_keys: [],
    };
    response.tools[0].input_contract.object_input_modes[0] = {
      ...response.tools[0].input_contract.object_input_modes[0],
      mode_id: "default",
      asset_input: {
        min_count: 1,
        max_count: 1,
        formats: ["h5ad"],
        assays: ["scRNA-seq"],
        input_levels: ["count_ready"],
        matrix_semantics: ["raw_counts"],
        required_metadata_keys: [],
      },
    };
    response.assets = [
      {
        id: "normalized-asset",
        label: "Normalized product H5AD",
        declaration: {
          assay: "scRNA-seq",
          matrix_semantics: "normalized_expression",
          input_level: "analysis_ready",
        },
      },
      {
        id: "raw-asset",
        label: "Raw-count product H5AD",
        declaration: {
          assay: "scRNA-seq",
          matrix_semantics: "raw_counts",
          input_level: "count_ready",
        },
      },
    ];
    response.selections["P0-03"] = {
      tool_id: "P0-03",
      mode_id: null,
      asset_ids: ["raw-asset"],
      object_inputs: [],
      measurement_spec_ref: null,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(response));
    const user = userEvent.setup();
    render(<AnalysisInputs {...props()} />);

    await openPanel(user);
    await user.selectOptions(screen.getByLabelText("Analysis tool"), "P0-03");
    await user.selectOptions(screen.getByLabelText("Input mode"), "default");

    expect(screen.getByLabelText("Registered H5AD asset")).toHaveValue("raw-asset");
    expect(screen.getByRole("option", { name: "Raw-count product H5AD" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Normalized product H5AD" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "raw counts" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "normalized expression" })).not.toBeInTheDocument();
  });

  it("honors multiple-role cardinality from the selected mode", async () => {
    const response = registry();
    response.tools[0].input_contract.object_input_modes[0].roles.push({
      role: "evidence_records",
      schema_refs: ["bridge://schemas/evidence-record-set/v0.1"],
      object_version_policy: "fixed",
      object_versions: ["0.1.0"],
      min_count: 1,
      max_count: 2,
    });
    response.objects.push(
      ...["a", "b", "c"].map((suffix) => ({
        id: `evidence-${suffix}`,
        label: `Evidence ${suffix.toUpperCase()}`,
        schema_ref: "bridge://schemas/evidence-record-set/v0.1",
        object_version: "0.1.0",
        source: "tool_output" as const,
        producer_tool_id: "P0-05",
      })),
    );
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(response));
    const user = userEvent.setup();
    render(<AnalysisInputs {...props()} />);

    await openPanel(user);
    await chooseContract(user);
    const picker = screen.getByLabelText("evidence records object");
    await user.selectOptions(picker, ["evidence-a", "evidence-b"]);

    expect((screen.getByRole("option", { name: /Evidence A/ }) as HTMLOptionElement).selected).toBe(true);
    expect((screen.getByRole("option", { name: /Evidence B/ }) as HTMLOptionElement).selected).toBe(true);
    expect(screen.getByRole("option", { name: /Evidence C/ })).toBeDisabled();
  });

  it("preserves an unsaved selection when a later lazy refresh completes", async () => {
    const fresh = registry();
    fresh.objects = fresh.objects.filter((object) => object.id !== "wrong-schema");
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(registry()))
      .mockResolvedValueOnce(jsonResponse(fresh));
    const user = userEvent.setup();
    render(<AnalysisInputs {...props()} />);

    await openPanel(user);
    await chooseContract(user);
    const objectSelect = screen.getByLabelText("product case object") as HTMLSelectElement;
    await user.selectOptions(objectSelect, "user-object");
    expect(objectSelect.value).toBe("user-object");

    await user.click(screen.getByText("Analysis inputs"));
    await openPanel(user);
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(2));

    expect((screen.getByLabelText("product case object") as HTMLSelectElement).value).toBe("user-object");
    expect(screen.getByText(/Save this new or changed selection/)).toBeInTheDocument();
  });

  it("does not allow an old session response to overwrite the current session registry", async () => {
    const first = deferred<Response>();
    const second = deferred<Response>();
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockImplementationOnce(() => first.promise)
      .mockImplementationOnce(() => second.promise);
    const user = userEvent.setup();
    const view = render(<AnalysisInputs {...props()} />);

    await openPanel(user);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/sessions/session-a/analysis-inputs",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );

    view.rerender(<AnalysisInputs {...props({ sessionId: "session-b" })} />);
    await user.click(screen.getByText("Analysis inputs"));
    await openPanel(user);
    second.resolve(jsonResponse(registry("P0-09", "Evidence reconciliation")));
    expect(await screen.findByRole("option", { name: "P0-09 · Evidence reconciliation" })).toBeInTheDocument();

    first.resolve(jsonResponse(registry("P0-06", "Stale program response")));
    await new Promise((resolve) => window.setTimeout(resolve, 0));

    expect(screen.queryByRole("option", { name: /Stale program response/ })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "P0-09 · Evidence reconciliation" })).toBeInTheDocument();
  });

  it("requires save before prepare, recovers after a save error, and keeps preparation non-approving", async () => {
    const savedRegistry = registry();
    savedRegistry.selections["P0-06"] = {
      tool_id: "P0-06",
      mode_id: "supplied_evidence",
      asset_ids: [],
      object_inputs: [{ role: "product_case", input_id: "user-object" }],
      measurement_spec_ref: null,
    };
    let saveAttempts = 0;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      if (init?.method === "POST" && path.endsWith("/analysis-inputs")) {
        saveAttempts += 1;
        if (saveAttempts === 1) return jsonResponse({ detail: "selection_conflict" }, 409);
        return jsonResponse(session());
      }
      if (init?.method === "POST" && path.endsWith("/prepare-analysis")) {
        return jsonResponse({
          ...session(),
          status: "awaiting_approval",
          plan: {
            id: "plan-1",
            digest: "digest-1",
            status: "proposed",
            summary: "Prepared selection",
            steps: [{
              id: "step-1",
              tool_id: "P0-06",
              label: "Program response",
              status: "pending",
              reason: null,
            }],
          },
        });
      }
      return jsonResponse(saveAttempts ? savedRegistry : registry());
    });
    const onSession = vi.fn();
    const user = userEvent.setup();
    render(<AnalysisInputs {...props({ onSession })} />);

    await openPanel(user);
    await chooseContract(user);
    await user.selectOptions(screen.getByLabelText("product case object"), "user-object");

    const prepare = screen.getByRole("button", { name: "Prepare plan" });
    expect(prepare).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Save selection" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("selection_conflict");
    expect(screen.getByRole("button", { name: "Save selection" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Save selection" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Prepare plan" })).toBeEnabled());
    const saveCall = fetchMock.mock.calls.find(
      ([path, init]) => String(path).endsWith("/analysis-inputs") && init?.method === "POST",
    );
    expect(saveCall?.[1]).toEqual(expect.objectContaining({
      body: JSON.stringify({
        tool_id: "P0-06",
        mode_id: "supplied_evidence",
        asset_ids: [],
        object_inputs: [{ role: "product_case", input_id: "user-object" }],
        measurement_spec_ref: null,
      }),
    }));

    await user.click(screen.getByRole("button", { name: "Prepare plan" }));
    await waitFor(() => expect(onSession).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: "awaiting_approval" }),
    ));
    const prepareCall = fetchMock.mock.calls.find(([path]) =>
      String(path).endsWith("/prepare-analysis"));
    expect(prepareCall?.[1]).toEqual(expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ tool_id: "P0-06" }),
    }));
    expect(screen.getByText("Plan prepared. It has not been approved or run.")).toBeInTheDocument();
  });

  it("reports a blocking prepare response without a false success notice", async () => {
    const savedRegistry = registry();
    savedRegistry.selections["P0-06"] = {
      tool_id: "P0-06",
      mode_id: "supplied_evidence",
      asset_ids: [],
      object_inputs: [{ role: "product_case", input_id: "user-object" }],
      measurement_spec_ref: null,
    };
    const blocked = {
      ...session(),
      status: "idle" as const,
      plan: null,
      error: "object_required:product_case",
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (init?.method === "POST" && String(input).endsWith("/prepare-analysis")) {
        return jsonResponse(blocked);
      }
      return jsonResponse(savedRegistry);
    });
    const onSession = vi.fn();
    const user = userEvent.setup();
    render(<AnalysisInputs {...props({ onSession })} />);

    await openPanel(user);
    await chooseContract(user);
    await user.click(screen.getByRole("button", { name: "Prepare plan" }));

    await waitFor(() => expect(onSession).toHaveBeenLastCalledWith(
      expect.objectContaining(blocked),
    ));
    expect(screen.queryByText("Plan prepared. It has not been approved or run.")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Plan not prepared: object required product case.",
    );
    expect(fetchMock.mock.calls.some(([path]) =>
      String(path).endsWith("/prepare-analysis"))).toBe(true);
  });

  it("offers contract-backed choices for ambiguous fixed schemas and versions", async () => {
    const response = registry();
    response.tools[0].input_contract.object_input_modes[0].roles = [{
      role: "evidence_sufficiency_profile",
      schema_refs: [
        "bridge://schemas/evidence-sufficiency-profile/v0.1",
        "bridge://schemas/evidence-sufficiency-profile/v0.2",
      ],
      object_version_policy: "fixed",
      object_versions: ["0.1.0", "0.2.0"],
      min_count: 1,
      max_count: 1,
    }];
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) =>
      init?.method === "POST" ? jsonResponse(session()) : jsonResponse(response),
    );
    const user = userEvent.setup();
    render(<AnalysisInputs {...props()} />);

    await openPanel(user);
    await chooseContract(user);
    await user.selectOptions(
      screen.getByLabelText("JSON schema"),
      "bridge://schemas/evidence-sufficiency-profile/v0.2",
    );
    await user.selectOptions(screen.getByLabelText("Object version"), "0.2.0");
    await user.upload(
      screen.getByLabelText("Register JSON for evidence sufficiency profile"),
      new File(["{}"], "profile.json", { type: "application/json" }),
    );

    await waitFor(() => expect(fetchMock.mock.calls.some(([path]) =>
      String(path).includes("object_version=0.2.0"))).toBe(true));
  });

  it.each([
    {
      label: "field-free fixed profile",
      role: {
        role: "evidence_sufficiency_profile",
        schema_refs: ["bridge://schemas/evidence-sufficiency-profile/v0.1"],
        object_version_policy: "fixed" as const,
        object_versions: ["0.1.0"],
        min_count: 1,
        max_count: 1,
      },
      payload: { profile_id: "profile-1", evidence_state: "measured" },
      schema: "bridge://schemas/evidence-sufficiency-profile/v0.1",
      version: "0.1.0",
    },
    {
      label: "version-field payload object",
      role: {
        role: "measurement_spec",
        schema_refs: ["bridge://schemas/measurement-spec/v0.2"],
        object_version_policy: "payload" as const,
        object_versions: [],
        min_count: 1,
        max_count: 1,
      },
      payload: { measurement_spec_id: "measurement-1", version: "2026.09" },
      schema: "bridge://schemas/measurement-spec/v0.2",
      version: "2026.09",
    },
  ])("registers a valid $label without requiring synthetic JSON fields", async ({
    role: uploadRole,
    payload,
    schema,
    version,
  }) => {
    const response = registry();
    response.tools[0].input_contract.object_input_modes[0].roles = [uploadRole];
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) =>
      init?.method === "POST" ? jsonResponse(session()) : jsonResponse(response),
    );
    const user = userEvent.setup();
    render(<AnalysisInputs {...props()} />);

    await openPanel(user);
    await chooseContract(user);
    await user.upload(
      screen.getByLabelText(`Register JSON for ${uploadRole.role.replaceAll("_", " ")}`),
      new File([JSON.stringify(payload)], "object.json", { type: "application/json" }),
    );

    await waitFor(() => expect(fetchMock.mock.calls.some(([path]) =>
      String(path).includes("/analysis-inputs/objects?"))).toBe(true));
    const [path] = fetchMock.mock.calls.find(([value]) =>
      String(value).includes("/analysis-inputs/objects?"))!;
    const query = new URL(String(path), "http://bridge.test").searchParams;
    expect(query.get("schema_ref")).toBe(schema);
    expect(query.get("object_version")).toBe(version);
  });

  it("rejects oversized scientific and metadata JSON before any registration request", async () => {
    const withAsset = registry();
    withAsset.tools[0].input_contract.object_input_modes[0].asset_input = {
      min_count: 1,
      max_count: 1,
      formats: ["h5ad"],
      assays: ["scRNA-seq"],
      input_levels: ["count_ready"],
      matrix_semantics: ["raw_counts"],
      required_metadata_keys: [],
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(withAsset));
    const user = userEvent.setup();
    render(
      <AnalysisInputs
        {...props({
          uploads: [{ id: "upload-1", name: "case.h5ad", kind: "h5ad", size: 12 }],
        })}
      />,
    );

    await openPanel(user);
    await chooseContract(user);

    const objectFile = new File(
      [new Uint8Array(2 * 1024 * 1024 + 1)],
      "large.json",
      { type: "application/json" },
    );
    await user.upload(screen.getByLabelText("Register JSON for product case"), objectFile);
    expect(await screen.findByRole("alert")).toHaveTextContent("exceeds the 2048 KiB");

    const metadataFile = new File(
      [new Uint8Array(32 * 1024 + 1)],
      "large-metadata.json",
      { type: "application/json" },
    );
    await user.upload(screen.getByLabelText("Choose advanced metadata JSON"), metadataFile);
    expect(await screen.findByRole("alert")).toHaveTextContent("exceeds the 32 KiB");

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("registers an uploaded H5AD with explicit declarations and opaque public fields", async () => {
    const response = registry();
    response.tools[0].input_contract.object_input_modes[0].asset_input = {
      min_count: 1,
      max_count: 1,
      formats: ["h5ad"],
      assays: ["scRNA-seq", "snRNA-seq"],
      input_levels: ["count_ready"],
      matrix_semantics: ["raw_counts"],
      required_metadata_keys: [],
    };
    const declaredAsset = {
      id: "asset-1",
      label: "Declared case H5AD",
      declaration: {
        upload_id: "upload-1",
        assay: "scRNA-seq",
        matrix_location: "layers/counts",
        matrix_semantics: "raw_counts",
        input_level: "count_ready",
      },
    };
    response.assets = [{ ...declaredAsset, declaration: null }];
    const registeredResponse = { ...response, assets: [declaredAsset] };
    let registered = false;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      if (init?.method === "POST") {
        registered = true;
        return jsonResponse(session());
      }
      return jsonResponse(registered ? registeredResponse : response);
    });
    const user = userEvent.setup();
    render(
      <AnalysisInputs
        {...props({
          uploads: [{ id: "upload-1", name: "case.h5ad", kind: "h5ad", size: 12 }],
        })}
      />,
    );

    await openPanel(user);
    await chooseContract(user);
    const pattern = screen.getByLabelText("Matrix location").getAttribute("pattern");
    if (!pattern) throw new Error("Matrix location pattern is missing.");
    expect(() => new RegExp(pattern, "v")).not.toThrow();
    const matrixLocation = new RegExp(`^(?:${pattern})$`, "v");
    expect(matrixLocation.test("X")).toBe(true);
    expect(matrixLocation.test("layers/counts")).toBe(true);
    expect(matrixLocation.test("layers/../counts")).toBe(false);
    expect(matrixLocation.test("layers/counts value")).toBe(false);
    expect(screen.queryByRole("option", { name: "Declared case H5AD" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "case.h5ad" })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Uploaded H5AD"), "upload-1");
    await user.selectOptions(screen.getByLabelText("Assay"), "scRNA-seq");
    await user.type(screen.getByLabelText("Matrix location"), "layers/counts");
    await user.selectOptions(screen.getByLabelText("Matrix semantics"), "raw_counts");
    await user.selectOptions(screen.getByLabelText("Input level"), "count_ready");
    await user.click(screen.getByRole("button", { name: "Register declaration" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([path, init]) =>
      String(path).endsWith("/analysis-inputs/assets") && init?.method === "POST")).toBe(true));
    expect(await screen.findByRole("option", { name: "Declared case H5AD" })).toBeInTheDocument();
    const registration = fetchMock.mock.calls.find(([path]) =>
      String(path).endsWith("/analysis-inputs/assets"));
    expect(registration?.[1]).toEqual(expect.objectContaining({
      body: JSON.stringify({
        upload_id: "upload-1",
        assay: "scRNA-seq",
        matrix_location: "layers/counts",
        matrix_semantics: "raw_counts",
        input_level: "count_ready",
        metadata: {},
      }),
    }));
  });

  it("blocks edits and submissions while the session is busy", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(registry()));
    const user = userEvent.setup();
    const view = render(<AnalysisInputs {...props()} />);

    await openPanel(user);
    await chooseContract(user);
    view.rerender(<AnalysisInputs {...props({ disabled: true })} />);

    expect(screen.getByLabelText("Analysis tool")).toBeDisabled();
    expect(screen.getByLabelText("Input mode")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save selection" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Prepare plan" })).toBeDisabled();
    expect(screen.getByLabelText("Register JSON for product case")).toBeDisabled();
  });

  it("recovers a failed lazy load through the visible retry control", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ detail: "registry_unavailable" }, 503))
      .mockResolvedValueOnce(jsonResponse(registry()));
    const user = userEvent.setup();
    render(<AnalysisInputs {...props()} />);

    await openPanel(user);
    expect(await screen.findByRole("alert")).toHaveTextContent("registry_unavailable");
    await user.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByRole("option", { name: "P0-06 · Program response" })).toBeInTheDocument();
    expect(screen.queryByText("registry_unavailable")).not.toBeInTheDocument();
  });
});
