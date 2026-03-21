import { useState, useEffect, useCallback } from 'react';
import type { Run, SqlUnit, Proposal } from '../types/v9';
import * as runService from '../services/runService';
import { isMockMode, MOCK_RUN_ID } from '../lib/mockHelper';

export function useRunDetail(runId: string | null) {
  const [run, setRun] = useState<Run | null>(null);
  const [sqlUnits, setSqlUnits] = useState<SqlUnit[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!runId) {
      setRun(null);
      setSqlUnits([]);
      setProposals([]);
      return;
    }
    
    setLoading(true);
    setError(null);
    try {
      const [runData, unitsData, proposalsData] = await Promise.all([
        runService.getRun(runId),
        runService.getSqlUnits(runId),
        runService.getProposals(runId)
      ]);
      setRun(runData);
      setSqlUnits(unitsData);
      setProposals(proposalsData);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load run details');
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => { refresh(); }, [refresh]);

  return { run, sqlUnits, proposals, loading, error, refresh };
}