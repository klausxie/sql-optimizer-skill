// Mode flag for development
export const isMockMode = import.meta.env.MODE === 'mock';

export const MOCK_RUN_ID = 'run_001';

export const MOCK_DATA_PATHS = {
  runsRoot: '/mockRuns',
  getRunDir: (runId: string) => `/mockRuns/${runId}`,
  getStatePath: (runId: string) => `/mockRuns/${runId}/supervisor/state.json`,
  getInitSqlUnitsPath: (runId: string) => `/mockRuns/${runId}/init/sql_units.json`,
  getParseUnitsWithBranchesPath: (runId: string) => `/mockRuns/${runId}/parse/sql_units_with_branches.json`,
  getProposalsPath: (runId: string) => `/mockRuns/${runId}/optimize/proposals.json`
};
