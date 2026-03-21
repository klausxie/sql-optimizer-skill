import { Alert, AlertDescription } from './ui/alert';
import { Badge } from './ui/badge';
import { CheckCircle, Clock, AlertTriangle } from 'lucide-react';
import type { Proposal } from '../types/v9';

interface ProposalCardProps {
  proposal: Proposal;
}

const verdictColors: Record<string, string> = {
  ACTIONABLE: 'border-green-500',
  NO_ACTION: 'border-slate-300',
  BLOCKED: 'border-amber-500'
};

export function ProposalCard({ proposal }: ProposalCardProps) {
  const { sqlKey, verdict, estimatedBenefit, confidence, suggestions, validated } = proposal;

  return (
    <Alert className={`border-l-4 ${verdictColors[verdict] ?? verdictColors.NO_ACTION}`}>
      <div className="flex items-center justify-between w-full">
        <span className="font-mono text-sm font-medium">{sqlKey}</span>
        <div className="flex items-center gap-2">
          {estimatedBenefit && <Badge variant="secondary">{estimatedBenefit}</Badge>}
          {confidence && <Badge variant="outline">{confidence}</Badge>}
          {validated ? (
            <CheckCircle className="w-4 h-4 text-green-600" />
          ) : (
            <Clock className="w-4 h-4 text-slate-400" />
          )}
        </div>
      </div>
      <AlertDescription className="mt-2">
        {suggestions && suggestions.length > 0 ? (
          <div className="space-y-2 mt-2">
            {suggestions.map((s, idx) => (
              <div key={idx} className="text-sm">
                <p className="font-medium text-slate-700">{s.type}: {s.rationale}</p>
                <div className="mt-1 p-2 bg-slate-50 rounded text-xs font-mono">
                  <p className="text-red-400 line-through">{s.originalSql}</p>
                  <p className="text-green-600">→ {s.suggestedSql}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <span className="text-slate-500">No suggestions available</span>
        )}
      </AlertDescription>
    </Alert>
  );
}
