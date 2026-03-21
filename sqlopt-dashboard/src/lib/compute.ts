export {
  computeProgress,
  deriveDisplayStatus,
  deriveRiskLevel,
  deriveSqlUnitStatus,
  STAGE_ORDER
} from '../types/v9';
import type { V9StageName, RiskIssue } from '../types/v9';

export function computeIssueCount(risks: RiskIssue[]): number {
  return risks.reduce((acc, r) => acc + r.risks.length, 0);
}

export function groupRisksBySeverity(risks: RiskIssue[]): Record<string, number> {
  const result: Record<string, number> = { HIGH: 0, MEDIUM: 0, LOW: 0 };
  risks.forEach(r => {
    r.risks.forEach(detail => {
      result[detail.severity]++;
    });
  });
  return result;
}
