import { useState, useEffect, useCallback } from 'react';
import type { SqlUnit } from '../types/v9';
import * as runService from '../services/runService';
import { isMockMode, MOCK_RUN_ID } from '../lib/mockHelper';

export function useSqlUnits(runId: string | null) {
  const [units, setUnits] = useState<SqlUnit[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!runId) {
      setUnits([]);
      return;
    }
    
    setLoading(true);
    setError(null);
    try {
      const data = await runService.getSqlUnits(runId);
      setUnits(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load SQL units');
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => { refresh(); }, [refresh]);

  return { units, loading, error, refresh };
}