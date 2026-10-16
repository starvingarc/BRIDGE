import { createReadStream, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Standalone workbench preview. The atlas tree is private and served only from local private_assets when present.
const treeFile = fileURLToPath(new URL('./private_assets/workbench/devtree.json', import.meta.url));

export default defineConfig({
  plugins: [react(), {
    name: 'local-workbench-tree',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if ((req.url ?? '').split('?')[0] !== '/workbench-data/devtree.json') return next();
        res.setHeader('Cache-Control', 'no-store');
        if (!existsSync(treeFile)) { res.statusCode = 404; res.end('Atlas tree unavailable in this environment'); return; }
        res.setHeader('Content-Type', 'application/json');
        createReadStream(treeFile).pipe(res);
      });
    },
  }],
  base: './',
  publicDir: 'public',
  server: { host: '127.0.0.1', port: 5179, strictPort: true, fs: { allow: ['..'] } },
  build: { outDir: 'workbench-dist', rolldownOptions: { input: 'workbench.html' } },
});
