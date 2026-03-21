import type { V9RunState, SqlUnit, RiskIssue, Proposal, PatchResult } from '../types/v9';
import { isMockMode } from '../lib/mockHelper';

export class FileReaderError extends Error {
  constructor(message: string, public path: string, public status?: number) {
    super(message);
    this.name = 'FileReaderError';
  }
}

function getMockPath(runId: string, suffix: string): string {
  return `/mockRuns/${runId}${suffix}`;
}

async function readFile(path: string): Promise<string> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new FileReaderError(`Failed to read ${path}`, path, response.status);
  }
  return response.text();
}

export async function readJson<T>(path: string): Promise<T> {
  const content = await readFile(path);
  return JSON.parse(content) as T;
}

export async function readRunState(runId: string): Promise<V9RunState> {
  const path = isMockMode 
    ? getMockPath(runId, '/supervisor/state.json')
    : `/api/file/runs/${runId}/supervisor/state.json`;
  return readJson<V9RunState>(path);
}

export async function readSqlUnits(runId: string): Promise<SqlUnit[]> {
  const path = isMockMode 
    ? getMockPath(runId, '/init/sql_units.json')
    : `/api/file/runs/${runId}/init/sql_units.json`;
  return readJson<SqlUnit[]>(path);
}

export async function readParseUnitsWithBranches(runId: string): Promise<SqlUnit[]> {
  const path = isMockMode 
    ? getMockPath(runId, '/parse/sql_units_with_branches.json')
    : `/api/file/runs/${runId}/parse/sql_units_with_branches.json`;
  try {
    return await readJson<SqlUnit[]>(path);
  } catch {
    return readSqlUnits(runId);
  }
}

export async function readRisks(runId: string): Promise<RiskIssue[]> {
  const path = isMockMode 
    ? getMockPath(runId, '/parse/risks.json')
    : `/api/file/runs/${runId}/parse/risks.json`;
  return readJson<RiskIssue[]>(path);
}

export async function readProposals(runId: string): Promise<Proposal[]> {
  const path = isMockMode 
    ? getMockPath(runId, '/optimize/proposals.json')
    : `/api/file/runs/${runId}/optimize/proposals.json`;
  return readJson<Proposal[]>(path);
}

export async function readPatches(runId: string): Promise<PatchResult[]> {
  const path = isMockMode 
    ? getMockPath(runId, '/patch/patches.json')
    : `/api/file/runs/${runId}/patch/patches.json`;
  return readJson<PatchResult[]>(path);
}
