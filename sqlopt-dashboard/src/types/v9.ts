// Core V9 State Types
export type V9RunStatus = 'pending' | 'running' | 'completed' | 'failed';
export type V9StageName = 'init' | 'parse' | 'recognition' | 'optimize' | 'patch';
export type RiskLevel = 'HIGH' | 'MEDIUM' | 'LOW';

export interface V9RunState {
  run_id: string;
  status: V9RunStatus;
  current_stage: V9StageName | null;
  completed_stages: V9StageName[];
  stage_results: Record<string, StageResult>;
  started_at: string;
  updated_at: string;
}

export interface StageResult {
  success: boolean;
  sql_units_count?: number;
  error?: string;
  [key: string]: unknown;
}

// Frontend Display Types
export interface Run {
  id: string;
  runId: string;
  status: RunDisplayStatus;
  currentStage: V9StageName | null;
  completedStages: V9StageName[];
  progress: number;
  startedAt: string;
  updatedAt: string;
  sqlCount: number;
  issueCount: number;
  runDir: string;
}

export type RunDisplayStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface SqlUnit {
  sqlKey: string;
  xmlPath: string;
  namespace: string;
  statementId: string;
  statementType: string;
  variantId: string;
  sql: string;
  riskFlags: string[];
  riskLevel: RiskLevel;
  branchCount: number;
  problemBranchCount: number;
  branches: SqlBranch[];
  baseline?: Baseline;
}

export interface SqlBranch {
  id: number;
  conditions: string[];
  sql: string;
  type: string;
  baseline?: BranchBaseline;
}

export interface Baseline {
  executionTime: string | null;
  rowsExamined: number | null;
  rowsReturned: number | null;
  usingIndex: boolean | null;
  type: string | null;
  planLines: string[];
  problematic: boolean;
}

export interface BranchBaseline extends Baseline {}

export interface RiskIssue {
  sqlKey: string;
  risks: RiskDetail[];
  prunedBranches: number[];
  recommendedForBaseline: boolean;
}

export interface RiskDetail {
  riskType: string;
  severity: RiskLevel;
  message: string | null;
  location: string | null;
  branchIds: number[];
}

export interface Proposal {
  sqlKey: string;
  issues: string[];
  verdict: string;
  estimatedBenefit: RiskLevel | null;
  confidence: RiskLevel | null;
  suggestions: Suggestion[];
  validated: boolean | null;
  validationStatus: string | null;
  originalSql: string | null;
  optimizedSql: string | null;
  riskFlags?: string[] | null;
}

export interface Suggestion {
  type: string;
  originalSql: string;
  suggestedSql: string;
  rationale: string;
}

export interface PatchResult {
  sqlKey: string;
  patchFiles: string[];
  applicable: boolean;
  originalSql: string;
  optimizedSql: string;
}

// Run Index
export interface RunIndex {
  schema_version: string;
  runs: RunIndexEntry[];
}

export interface RunIndexEntry {
  run_id: string;
  run_dir: string;
  updated_at: string;
}

// Stage Order Constant
export const STAGE_ORDER: V9StageName[] = ['init', 'parse', 'recognition', 'optimize', 'patch'];

// Computation Functions
export function computeProgress(completedStages: V9StageName[]): number {
  return Math.round((completedStages.length / STAGE_ORDER.length) * 100);
}

export function deriveDisplayStatus(state: V9RunState): RunDisplayStatus {
  if (state.status === 'failed') return 'failed';
  if (state.status === 'completed') return 'completed';
  if (state.status === 'pending') return 'pending';
  if (state.status === 'running') {
    const currentIdx = STAGE_ORDER.indexOf(state.current_stage ?? '');
    return currentIdx >= STAGE_ORDER.length - 1 ? 'completed' : 'running';
  }
  return 'pending';
}

const HIGH_RISK_FLAGS = ['PREFIX_WILDCARD', 'CONCAT_WILDCARD', 'FUNCTION_WRAP', 'SUFFIX_WILDCARD'];
const MEDIUM_RISK_FLAGS = ['DOLLAR_SUBSTITUTION', 'LIMIT_MISSING', 'OFFSET_MISSING'];

export function deriveRiskLevel(riskFlags: string[]): RiskLevel {
  if (riskFlags.some(f => HIGH_RISK_FLAGS.includes(f))) return 'HIGH';
  if (riskFlags.some(f => MEDIUM_RISK_FLAGS.includes(f))) return 'MEDIUM';
  return 'LOW';
}

export type SqlUnitStatus = 'discovered' | 'parsed' | 'analyzed' | 'optimized' | 'patched';

export function deriveSqlUnitStatus(sqlKey: string, completedStages: V9StageName[]): SqlUnitStatus {
  if (!completedStages.includes('init')) return 'discovered';
  if (!completedStages.includes('parse')) return 'parsed';
  if (!completedStages.includes('recognition')) return 'analyzed';
  if (!completedStages.includes('optimize')) return 'optimized';
  return 'patched';
}
