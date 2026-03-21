import * as fileReader from './fileReader';
import * as cliRunner from './cliRunner';
import type { Run, SqlUnit, Proposal, PatchResult, V9RunState } from '../types/v9';
import { deriveDisplayStatus, deriveRiskLevel, computeProgress, deriveSqlUnitStatus, STAGE_ORDER } from '../types/v9';

export { fileReader, cliRunner };

// High-level read operations

export async function getRun(runId: string): Promise<Run | null> {
  try {
    const state = await fileReader.readRunState(runId);
    return stateToRun(runId, state);
  } catch {
    return null;
  }
}

export async function getSqlUnits(runId: string): Promise<SqlUnit[]> {
  const units = await fileReader.readParseUnitsWithBranches(runId);
  return units.map(u => ({
    ...u,
    riskLevel: deriveRiskLevel(u.riskFlags ?? []),
    branchCount: (u as any).branchCount ?? 0,
    problemBranchCount: (u as any).problemBranchCount ?? 0,
    branches: (u as any).branches ?? []
  }));
}

export async function getProposals(runId: string): Promise<Proposal[]> {
  try {
    return await fileReader.readProposals(runId);
  } catch {
    return [];
  }
}

export async function getPatches(runId: string): Promise<PatchResult[]> {
  try {
    return await fileReader.readPatches(runId);
  } catch {
    return [];
  }
}

// Write operations (via CLI)

export async function startRun(configPath: string, runId?: string) {
  return cliRunner.startRun(configPath, runId);
}

export async function resumeRun(runId: string) {
  return cliRunner.resumeRun(runId);
}

export async function applyPatches(runId: string) {
  return cliRunner.applyPatches(runId);
}

// Helper

function stateToRun(runId: string, state: V9RunState): Run {
  const completedStages = state.completed_stages;
  return {
    id: runId,
    runId: state.run_id,
    status: deriveDisplayStatus(state),
    currentStage: state.current_stage,
    completedStages,
    progress: computeProgress(completedStages),
    startedAt: state.started_at,
    updatedAt: state.updated_at,
    sqlCount: state.stage_results['init']?.sql_units_count ?? 0,
    issueCount: state.stage_results['parse']?.issue_count ?? 0,
    runDir: `runs/${runId}`
  };
}
