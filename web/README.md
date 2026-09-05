# BRIDGE Web preview

Private React/Vite client for the authenticated BRIDGE conversational preview. The server owns authentication, sessions, uploads, plans, execution and artifacts; this client only consumes the same-origin `/api` contract.

## Commands

Use Node.js 22.12 or newer.

```bash
npm ci
npm test
npm run build
```

For development, start the BRIDGE Web service on loopback port 8765, then:

```bash
npm run dev
```

Vite listens on `127.0.0.1:5173` and proxies `/api` to `127.0.0.1:8765`. Production static files are emitted to `web/dist` for FastAPI to serve.

## Security and behavior

- The login token is posted once and is never persisted by the client. Authenticated requests use the server cookie with same-origin credentials.
- Messages are rendered as Markdown without raw HTML or model-authored images. Artifacts use registered same-origin session URLs; no arbitrary URL or HTML iframe is rendered.
- The UI contains no fabricated scientific outcomes. Figures, tables, evidence and downloads appear only when returned by the server.
- A proposed plan can be approved only by sending its exact server-provided plan ID and digest.
