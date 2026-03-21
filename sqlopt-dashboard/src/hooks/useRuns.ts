import { useState, useEffect, useCallback } from 'react';
import type { Run } from '../types/v9';
import * as runService from '../services/runService';
import { isMockMode, MOCK_RUN_ID } from '../lib/mockHelper';

export function useRuns() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (isMockMode) {
        // In mock mode, return mock run
        const mockRun = await runService.getRun(MOCK_RUN_ID);
        setRuns(mockRun ? [mockRun] : []);
      } else {
        // In real mode, would scan runs/ directory
        // For now, return empty - real implementation would list runs
        setRuns([]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load runs');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { runs, loading, error, refresh };
}