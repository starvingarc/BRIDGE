import { createReadStream, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react(), {
    name: 'local-anatomy-evidence',
    configureServer(server) {
      const files: Record<string, [string, string]> = {
        '/anatomy-evidence/tissue.png': ['section2-tissue-overlay.png', 'image/png'],
        '/anatomy-evidence/sagittal.jpg': ['atlas-cs15-sagittal-11.jpg', 'image/jpeg'],
        '/anatomy-evidence/frontal.jpg': ['atlas-cs15-frontal-24.jpg', 'image/jpeg'],
      };
      server.middlewares.use((req, res, next) => {
        const file = files[(req.url ?? '').split('?')[0]];
        if (!file) return next();
        const path = fileURLToPath(new URL(`./private_assets/localization/${file[0]}`, import.meta.url));
        res.setHeader('Cache-Control', 'no-store');
        if (!existsSync(path)) { res.statusCode = 404; res.end('Evidence unavailable in this environment'); return; }
        res.setHeader('Content-Type', file[1]);
        const stream = createReadStream(path);
        stream.on('error', () => { res.destroy(); });
        stream.pipe(res);
      });
    },
  }],
  publicDir: false,
  server: { host: '127.0.0.1', port: 5178, strictPort: true },
  build: { outDir: 'anatomy-dist', rolldownOptions: { input: 'anatomy.html' } },
});
