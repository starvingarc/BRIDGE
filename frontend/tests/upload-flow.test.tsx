import { testPrincipal } from "./account-fixture";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthRoot } from "../src/AuthRoot";
import type { Session } from "../src/types";

const config = (size = 1024 ** 2) => ({ max_upload_bytes: size, max_h5ad_logical_bytes: size, max_h5ad_dataset_elements: 1000 });
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const session = (id = "one"): Session => ({ id, title: "Study " + id, status: "idle", updated_at: "", messages: [], uploads: [], plan: null, artifacts: [], error: null, input_review_required: false, pending_input_change: null });
function deferred() {
  let resolve!: (response: Response) => void;
  const promise = new Promise<Response>(done => { resolve = done; });
  return { promise, resolve };
}
async function setup(getConfig: () => Promise<Response> = async () => json(config()), post: () => Promise<Response> = async () => json(session()), secondSession: () => Promise<Response> = async () => json(session("two"))) {
  const uploads: RequestInit[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = String(input);
    if (path === "/api/auth/config") return json({mode: "accounts", notice: "Synthetic testing notice", notice_version: "v1"});
    if (path === "/api/me") return json({user: testPrincipal});
    if (path === "/api/researches") return json({researches: []});
    if (path === "/api/config") return getConfig();
    if (path === "/api/sessions") return json({ sessions: [session(), session("two")] });
    if (path === "/api/logout") return json({ authenticated: false });
    if (path.endsWith("/uploads")) { uploads.push(init!); return post(); }
    if (path === "/api/sessions/one") return json(session());
    if (path === "/api/sessions/two") return secondSession();
    throw new Error(path);
  });
  render(<AuthRoot />);
  await userEvent.click(await screen.findByRole("button", {name: "打开历史会话"}));
  return uploads;
}
const file = (size: number) => {
  const value = new File(["x"], "research.h5ad");
  Object.defineProperty(value, "size", { value: size });
  return value;
};
async function select(size: number) {
  await screen.findByText(/H5AD.*per file/);
  fireEvent.change(screen.getByLabelText("Choose H5AD file"), { target: { files: [file(size)] } });
}
beforeEach(() => localStorage.clear());

it("rejects one byte over and preserves exact-limit and small uploads", async () => {
  const uploads = await setup();
  await select(1024 ** 2 + 1);
  expect(await screen.findByText(/1,048,577.*current limit/)).toBeVisible();
  expect(uploads).toHaveLength(0);
  await select(1024 ** 2);
  await waitFor(() => expect(uploads).toHaveLength(1));
  await screen.findByText(/File received/);
  await select(1);
  await waitFor(() => expect(uploads).toHaveLength(2));
});
it("rechecks dynamic limits before sending any body", async () => {
  let reads = 0;
  const uploads = await setup(async () => json(config(++reads === 1 ? 4 * 1024 ** 3 : 1024 ** 2)));
  await select(2 * 1024 ** 2);
  expect(await screen.findByText(/current limit is 1 MiB/)).toBeVisible();
  expect(uploads).toHaveLength(0);
});
it("fails closed on invalid initial config and offers a retry", async () => {
  let reads = 0;
  const uploads = await setup(async () => json(++reads === 1 ? {} : config()));
  expect(await screen.findByText(/Could not check the upload limit/)).toBeVisible();
  expect(screen.getByLabelText("Upload H5AD")).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Retry upload limit" }));
  await select(1);
  await waitFor(() => expect(uploads).toHaveLength(1));
});
it("does not use cached limits after a failed refresh", async () => {
  let reads = 0;
  const uploads = await setup(async () => ++reads === 1 ? json(config()) : json({ detail: "private_error" }, 503));
  await select(1);
  expect(await screen.findByText(/Could not check the upload limit/)).toBeVisible();
  expect(uploads).toHaveLength(0);
  expect(screen.getByLabelText("Upload H5AD")).toBeDisabled();
});
it("locks other actions while checking and uploading without a percentage", async () => {
  let reads = 0;
  const check = deferred(), transfer = deferred();
  const uploads = await setup(async () => ++reads === 1 ? json(config()) : check.promise, () => transfer.promise);
  await select(1);
  expect(await screen.findByText(/Checking the current upload limit/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", {name: "researcher"}));
  expect(screen.getByRole("button", { name: "退出登录" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Study two" })).toBeDisabled();
  await act(async () => check.resolve(json(config())));
  expect(await screen.findByText(/Uploading.*keep this page open/i)).toBeVisible();
  expect(screen.queryByText(/\d+%/)).not.toBeInTheDocument();
  expect(uploads).toHaveLength(1);
  await act(async () => transfer.resolve(json(session())));
  expect(await screen.findByText(/File received/)).toBeVisible();
  expect(screen.getByRole("button", { name: "退出登录" })).toBeEnabled();
});
it("ignores config responses from the previous session", async () => {
  const old = deferred(); let reads = 0;
  await setup(async () => ++reads === 1 ? old.promise : json(config(2 * 1024 ** 2)));
  await userEvent.click(await screen.findByRole("button", { name: "Study two" }));
  await screen.findByText(/2 MiB.*per file/);
  await act(async () => old.resolve(json(config(1024 ** 2))));
  expect(screen.getByText(/2 MiB.*per file/)).toBeVisible();
});
it("ignores late config authentication failures after logout", async () => {
  const old = deferred();
  await setup(() => old.promise);
  await userEvent.click(await screen.findByRole("button", {name: "researcher"}));
  await userEvent.click(screen.getByRole("button", { name: "退出登录" }));
  await screen.findByRole("button", { name: "登录" });
  await act(async () => old.resolve(json({}, 401)));
  expect(screen.getByRole("button", { name: "登录" })).toBeVisible();
  expect(screen.queryByText(/Could not check/)).not.toBeInTheDocument();
});
it("expires authentication during the preflight without uploading", async () => {
  let reads = 0;
  const uploads = await setup(async () => ++reads === 1 ? json(config()) : json({}, 401));
  await select(1);
  expect(await screen.findByRole("button", { name: "登录" })).toBeVisible();
  expect(uploads).toHaveLength(0);
});

it("keeps config usable when a session switch fails", async () => {
  const old = deferred();
  await setup(() => old.promise, undefined, async () => json({ detail: "temporary_unavailable" }, 503));
  await userEvent.click(await screen.findByRole("button", { name: "Study two" }));
  await screen.findByText("temporary_unavailable");
  await act(async () => old.resolve(json(config())));
  expect(await screen.findByText(/1 MiB.*per file/)).toBeVisible();
});
it("accepts a file after the current limit is increased", async () => {
  let reads = 0;
  const uploads = await setup(async () => json(config(++reads === 1 ? 1024 ** 2 : 4 * 1024 ** 3)));
  await select(2 * 1024 ** 2);
  await waitFor(() => expect(uploads).toHaveLength(1));
});
it("does not show raw upload failure details and unlocks for another try", async () => {
  await setup(undefined, async () => json({ detail: "/private/internal/path", user_message: "arbitrary raw message" }, 400));
  await select(1);
  expect(await screen.findByText(/Check that it is a valid, supported H5AD/)).toBeVisible();
  expect(screen.queryByText(/private\/internal|arbitrary raw/)).not.toBeInTheDocument();
  expect(screen.getByLabelText("Upload H5AD")).toBeEnabled();
});
