import type { Principal } from "../src/api";
export const testPrincipal: Principal = {id: "test-user-id", username: "researcher", role: "user", must_change_password: false};
export const onTestSignedOut = () => undefined;
