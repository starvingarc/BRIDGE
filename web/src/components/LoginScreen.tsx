import { ArrowRight, LockKeyhole } from "lucide-react";
import { type FormEvent, useState } from "react";

type Props = {
  busy: boolean;
  error: string | null;
  onLogin: (token: string) => Promise<void>;
};

export function LoginScreen({ busy, error, onLogin }: Props) {
  const [token, setToken] = useState("");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!token.trim() || busy) return;
    await onLogin(token);
  };

  return (
    <main className="login-shell">
      <section className="login-card" aria-labelledby="login-title">
        <div className="brand">BRIDGE</div>
        <div className="login-icon" aria-hidden="true">
          <LockKeyhole />
        </div>
        <h1 id="login-title">Private research preview</h1>
        <p>Enter the access token provided by the preview operator.</p>
        <form onSubmit={submit}>
          <label htmlFor="access-token">Access token</label>
          <div className="login-input-row">
            <input
              id="access-token"
              name="token"
              type="password"
              autoComplete="current-password"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              disabled={busy}
              autoFocus
            />
            <button type="submit" disabled={busy || !token.trim()} aria-label="Sign in">
              <ArrowRight aria-hidden="true" />
            </button>
          </div>
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
        </form>
        <p className="login-footnote">Your token stays in this sign-in request and is not stored in the browser.</p>
      </section>
    </main>
  );
}
