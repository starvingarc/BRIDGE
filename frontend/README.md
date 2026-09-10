# BRIDGE frontend

React/Vite browser client for the private BRIDGE Web interface.
The Python service remains in `src/bridge/web/`; the browser consumes its
same-origin API.

## Build and test

Use Node.js 22.12 or newer. From the repository root:

~~~bash
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run build
~~~

The build writes `frontend/dist/`. Configure the Python service's
`BRIDGE_WEB_STATIC_DIR` with that directory's absolute path.

## Local development

With the privately configured BRIDGE service on loopback port 8765:

~~~bash
npm --prefix frontend run dev
~~~

Vite listens on `127.0.0.1:5173` and proxies `/api` to
`127.0.0.1:8765`. Configure the service origin to match the browser origin.

Authentication, approval, assessment, versioning and artifact behavior are
defined in the [Web guide](../docs/web-preview.md). Repository contribution and
maintenance requirements live in [AGENTS](../AGENTS.md).
