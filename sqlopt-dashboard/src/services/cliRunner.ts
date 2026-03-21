export interface CliResult {
  success: boolean;
  stdout: string;
  stderr: string;
  exitCode: number;
}

export async function startRun(configPath: string, runId?: string): Promise<CliResult> {
  const response = await fetch('/api/run/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ configPath, runId })
  });
  return response.json();
}

export async function resumeRun(runId: string): Promise<CliResult> {
  const response = await fetch('/api/run/resume', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ runId })
  });
  return response.json();
}

export async function applyPatches(runId: string): Promise<CliResult> {
  const response = await fetch('/api/run/apply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ runId })
  });
  return response.json();
}
