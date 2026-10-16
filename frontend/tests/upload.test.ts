import { api } from "../src/api";
import { formatBytes, parseUploadLimits, uploadErrorMessage } from "../src/upload";

const limits = { max_upload_bytes: 4 * 1024 ** 3, max_h5ad_logical_bytes: 2 * 1024 ** 3, max_h5ad_dataset_elements: 100_000_000 };
describe("upload contract", () => {
  it("validates all limits without accepting coerced or unsafe values", () => {
    expect(parseUploadLimits(limits)).toEqual(limits);
    for (const value of [null, {}, { ...limits, max_upload_bytes: "4000" }, { ...limits, max_upload_bytes: 0 },
      { ...limits, max_h5ad_logical_bytes: -1 }, { ...limits, max_h5ad_dataset_elements: 1.5 },
      { ...limits, max_upload_bytes: Number.MAX_SAFE_INTEGER + 1 }]) {
      expect(() => parseUploadLimits(value)).toThrow();
    }
  });
  it("uses readable binary units without hiding a one-byte difference", () => {
    expect(formatBytes(4 * 1024 ** 3)).toContain("4 GiB");
    expect(formatBytes(128 * 1024 ** 2)).toContain("128 MiB");
    expect(formatBytes(1024 ** 2 + 1)).toContain("1,048,577");
  });
  it("distinguishes body limits, H5AD resource limits, and untrusted errors", () => {
    expect(uploadErrorMessage(413, { detail: "request_too_large", max_upload_bytes: 128 * 1024 ** 2 })).toContain("128 MiB");
    expect(uploadErrorMessage(413, { detail: "h5ad_resource_limit", reason: "h5ad_logical_size_limit", ...limits })).toMatch(/expanded.*2 GiB/i);
    expect(uploadErrorMessage(413, { detail: "h5ad_resource_limit", reason: "h5ad_dataset_element_limit", ...limits })).toContain("100,000,000");
    expect(uploadErrorMessage(413, null)).toMatch(/server or.*proxy/i);
    expect(uploadErrorMessage(400, { detail: "/private/path", user_message: "secret" })).not.toMatch(/secret|private/);
  });
  it("fetches authenticated config without using browser caches", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(limits)));
    expect(await api.uploadConfig()).toEqual(limits);
    expect(fetch).toHaveBeenCalledWith("/api/config", expect.objectContaining({ credentials: "same-origin", cache: "no-store" }));
  });
  it.each([
    [JSON.stringify({ detail: "request_too_large", max_upload_bytes: 128 * 1024 ** 2 }), "128 MiB"],
    ["<html>proxy private error</html>", "proxy"],
    [JSON.stringify({ detail: "h5ad_resource_limit", reason: "h5ad_dataset_element_limit", ...limits }), "100,000,000"]
  ])("handles upload 413 response %#", async (body, message) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(body, { status: 413 }));
    await expect(api.upload("s", new File(["x"], "data.h5ad"))).rejects.toThrow(message);
  });
});
