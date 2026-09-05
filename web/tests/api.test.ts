import { ApiError, api } from "../src/api";

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });

describe("API client", () => {
  it("keeps authentication in a same-origin cookie and sends the login token only in the request body", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ authenticated: true }),
    );

    await api.login("preview-secret");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/login",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({ token: "preview-secret" }),
      }),
    );
  });

  it("binds approval to the exact plan id and digest", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ id: "session-1" }),
    );

    await api.approvePlan("session-1", "plan-7", "sha256:digest");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/sessions/session-1/approve",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ plan_id: "plan-7", plan_digest: "sha256:digest" }),
      }),
    );
  });

  it("uses multipart FormData for uploads without overriding its content type", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ id: "session-1" }),
    );
    const file = new File(["content"], "sample.h5ad", { type: "application/x-hdf5" });

    await api.upload("session-1", file);

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(request.body).toBeInstanceOf(FormData);
    expect((request.headers as Headers).has("Content-Type")).toBe(false);
  });

  it("shows a stable server detail and hides unknown non-JSON failures", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ detail: "invalid_upload_type" }, { status: 400 }))
      .mockResolvedValueOnce(new Response("<private traceback>", { status: 500 }));

    await expect(api.createSession()).rejects.toEqual(
      expect.objectContaining<Partial<ApiError>>({ status: 400, message: "invalid_upload_type" }),
    );
    await expect(api.createSession()).rejects.toEqual(
      expect.objectContaining<Partial<ApiError>>({
        status: 500,
        message: "The request could not be completed. Please try again.",
      }),
    );
  });
});
