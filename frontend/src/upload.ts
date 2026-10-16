export type UploadLimits = {
  max_upload_bytes: number;
  max_h5ad_logical_bytes: number;
  max_h5ad_dataset_elements: number;
};

const positiveInteger = (value: unknown): value is number =>
  typeof value === "number" && Number.isSafeInteger(value) && value > 0;

export function parseUploadLimits(value: unknown): UploadLimits {
  const data = value as Partial<UploadLimits> | null;
  if (!data || !positiveInteger(data.max_upload_bytes) || !positiveInteger(data.max_h5ad_logical_bytes)
    || !positiveInteger(data.max_h5ad_dataset_elements)) throw new Error("Invalid upload limits");
  return { max_upload_bytes: data.max_upload_bytes, max_h5ad_logical_bytes: data.max_h5ad_logical_bytes,
    max_h5ad_dataset_elements: data.max_h5ad_dataset_elements };
}

export function formatBytes(bytes: number): string {
  const unit = bytes >= 1024 ** 3 ? "GiB" : "MiB";
  const size = bytes / (unit === "GiB" ? 1024 ** 3 : 1024 ** 2);
  return size.toLocaleString("en-US", { maximumFractionDigits: 2 }) + " " + unit
    + " (" + bytes.toLocaleString("en-US") + " bytes)";
}

export function uploadErrorMessage(status: number, value: unknown): string {
  if (status === 401) return "Your sign-in has expired. Please sign in again.";
  const body = value as Record<string, unknown> | null;
  if (status === 413) {
    if (body?.detail === "h5ad_resource_limit") {
      if (body.reason === "h5ad_logical_size_limit") {
        return "The data inside this H5AD exceeds the expanded-data limit"
          + (positiveInteger(body.max_h5ad_logical_bytes) ? " of " + formatBytes(body.max_h5ad_logical_bytes) : "")
          + ". A smaller compressed file will not resolve this. Ask the operator to review the data capacity.";
      }
      if (body.reason === "h5ad_dataset_element_limit") {
        return "A dataset inside this H5AD exceeds the element limit"
          + (positiveInteger(body.max_h5ad_dataset_elements) ? " of " + body.max_h5ad_dataset_elements.toLocaleString("en-US") : "")
          + ". Ask the operator to review the data capacity; compressing the file will not resolve this.";
      }
      return "The data inside this H5AD exceeds the current processing capacity. Ask the operator to review the data limits.";
    }
    if (body?.detail === "request_too_large" && positiveInteger(body.max_upload_bytes)) {
      return "The file exceeds the current upload limit of " + formatBytes(body.max_upload_bytes)
        + ". Choose a smaller file or ask the operator to review the upload limit.";
    }
    return "The server or an upload proxy rejected this file as too large. Ask the operator to check both upload limits before trying again.";
  }
  if (status === 409) return "This analysis cannot accept another upload right now. Wait for the current work to finish and try again.";
  if (status === 400 || status === 422) return "This file could not be accepted as H5AD. Check that it is a valid, supported H5AD file and try again.";
  return "The file could not be uploaded. Check the connection and try again.";
}
