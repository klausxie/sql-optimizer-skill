import { defineConfig } from 'vite';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import react from "@vitejs/plugin-react";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function cliProxyPlugin() {
  return {
    name: 'cli-proxy',
    configureServer(server: any) {
      server.middlewares.use('/mockRuns/', async (req: any, res: any) => {
        try {
          const filePath = req.url!;
          const projectRoot = path.resolve(__dirname, '.');
          const fullPath = path.join(projectRoot, 'mockRuns', filePath.replace('/mockRuns/', ''));
          
          const fs = await import('fs/promises');
          const content = await fs.readFile(fullPath);
          
          const ext = path.extname(fullPath);
          const contentType = ext === '.json' ? 'application/json' : 'text/plain';
          res.setHeader('Content-Type', contentType);
          res.end(content);
        } catch (e) {
          res.statusCode = 404;
          res.end('Not found');
        }
      });

      server.middlewares.use('/api/run/start', async (req: any, res: any) => {
        if (req.method !== 'POST') {
          res.statusCode = 405;
          res.end('Method Not Allowed');
          return;
        }
        
        let body = '';
        req.on('data', (chunk: any) => { body += chunk; });
        req.on('end', () => {
          try {
            const { configPath, runId } = JSON.parse(body || '{}');
            const projectRoot = path.resolve(__dirname, '../');
            
            const args = ['run', '--config', configPath];
            if (runId) {
              args.push('--run-id', runId);
            }
            
            const proc = spawn('sqlopt-cli', args, {
              cwd: projectRoot,
              shell: true
            });
            
            let stdout = '';
            let stderr = '';
            
            proc.stdout.on('data', (data) => { stdout += data.toString(); });
            proc.stderr.on('data', (data) => { stderr += data.toString(); });
            
            proc.on('close', (code) => {
              res.setHeader('Content-Type', 'application/json');
              res.statusCode = code === 0 ? 200 : 500;
              res.end(JSON.stringify({
                success: code === 0,
                exitCode: code,
                stdout,
                stderr
              }));
            });
          } catch (e) {
            res.statusCode = 500;
            res.end(JSON.stringify({ error: String(e) }));
          }
        });
      });

      server.middlewares.use('/api/run/resume', async (req: any, res: any) => {
        if (req.method !== 'POST') {
          res.statusCode = 405;
          res.end('Method Not Allowed');
          return;
        }
        
        let body = '';
        req.on('data', (chunk: any) => { body += chunk; });
        req.on('end', () => {
          try {
            const { runId } = JSON.parse(body || '{}');
            const projectRoot = path.resolve(__dirname, '../');
            
            const args = ['resume', '--run-id', runId];
            
            const proc = spawn('sqlopt-cli', args, {
              cwd: projectRoot,
              shell: true
            });
            
            let stdout = '';
            let stderr = '';
            
            proc.stdout.on('data', (data) => { stdout += data.toString(); });
            proc.stderr.on('data', (data) => { stderr += data.toString(); });
            
            proc.on('close', (code) => {
              res.setHeader('Content-Type', 'application/json');
              res.statusCode = code === 0 ? 200 : 500;
              res.end(JSON.stringify({
                success: code === 0,
                exitCode: code,
                stdout,
                stderr
              }));
            });
          } catch (e) {
            res.statusCode = 500;
            res.end(JSON.stringify({ error: String(e) }));
          }
        });
      });

      server.middlewares.use('/api/run/apply', async (req: any, res: any) => {
        if (req.method !== 'POST') {
          res.statusCode = 405;
          res.end('Method Not Allowed');
          return;
        }
        
        let body = '';
        req.on('data', (chunk: any) => { body += chunk; });
        req.on('end', () => {
          try {
            const { runId } = JSON.parse(body || '{}');
            const projectRoot = path.resolve(__dirname, '../');
            
            const args = ['apply', '--run-id', runId];
            
            const proc = spawn('sqlopt-cli', args, {
              cwd: projectRoot,
              shell: true
            });
            
            let stdout = '';
            let stderr = '';
            
            proc.stdout.on('data', (data) => { stdout += data.toString(); });
            proc.stderr.on('data', (data) => { stderr += data.toString(); });
            
            proc.on('close', (code) => {
              res.setHeader('Content-Type', 'application/json');
              res.statusCode = code === 0 ? 200 : 500;
              res.end(JSON.stringify({
                success: code === 0,
                exitCode: code,
                stdout,
                stderr
              }));
            });
          } catch (e) {
            res.statusCode = 500;
            res.end(JSON.stringify({ error: String(e) }));
          }
        });
      });

      server.middlewares.use('/api/file/', async (req: any, res: any) => {
        try {
          const filePath = req.url!.replace('/api/file/', '');
          const projectRoot = path.resolve(__dirname, '../');
          const fullPath = path.join(projectRoot, filePath);
          
          const fs = await import('fs/promises');
          const content = await fs.readFile(fullPath, 'utf-8');
          
          res.setHeader('Content-Type', 'application/json');
          res.end(content);
        } catch (e) {
          res.statusCode = 404;
          res.end(JSON.stringify({ error: String(e) }));
        }
      });
    }
  };
}

export default defineConfig({
  plugins: [react(), cliProxyPlugin()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    fs: {
      allow: ['../../']
    }
  }
});
