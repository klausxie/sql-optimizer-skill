// Resolves paths relative to project root (parent of sqlopt-dashboard)
export function getProjectRoot(): string {
  const url = new URL('../../', import.meta.url);
  return url.pathname;
}

export function getRunsRoot(): string {
  return getProjectRoot() + 'runs';
}

export function getRunDir(runId: string): string {
  return `${getRunsRoot()}/${runId}`;
}

// Supervisor paths
export function getStatePath(runId: string): string {
  return `${getRunDir(runId)}/supervisor/state.json`;
}

export function getMetaPath(runId: string): string {
  return `${getRunDir(runId)}/supervisor/meta.json`;
}

export function getPlanPath(runId: string): string {
  return `${getRunDir(runId)}/supervisor/plan.json`;
}

// Stage output paths
export function getInitSqlUnitsPath(runId: string): string {
  return `${getRunDir(runId)}/init/sql_units.json`;
}

export function getParseUnitsWithBranchesPath(runId: string): string {
  return `${getRunDir(runId)}/parse/sql_units_with_branches.json`;
}

export function getParseRisksPath(runId: string): string {
  return `${getRunDir(runId)}/parse/risks.json`;
}

export function getBaselinesPath(runId: string): string {
  return `${getRunDir(runId)}/recognition/baselines.json`;
}

export function getProposalsPath(runId: string): string {
  return `${getRunDir(runId)}/optimize/proposals.json`;
}

export function getPatchesPath(runId: string): string {
  return `${getRunDir(runId)}/patch/patches.json`;
}

export function getReportPath(runId: string): string {
  return `${getRunDir(runId)}/overview/report.summary.md`;
}
