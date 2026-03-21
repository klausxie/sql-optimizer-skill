import { useState, useEffect, useCallback } from 'react';
import type { Proposal } from '../types/v9';
import * as runService from '../services/runService';
import { isMockMode, MOCK_RUN_ID } from '../lib/mockHelper';

export function useProposals(runId: string | null) {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!runId) {
      setProposals([]);
      return;
    }
    
    setLoading(true);
    setError(null);
    try {
      const data = await runService.getProposals(runId);
      setProposals(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load proposals');
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => { refresh(); }, [refresh]);

  return { proposals, loading, error, refresh };
}