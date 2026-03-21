import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { SqlUnit } from '../types/v9';
import { Card, CardContent } from './ui/card';
import { RiskBadge } from './RiskBadge';

interface SqlUnitDetailProps {
  unit: SqlUnit;
}

export function SqlUnitDetail({ unit }: SqlUnitDetailProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card className="mb-2">
      <CardContent className="pt-4">
        <div className="flex items-start justify-between cursor-pointer" onClick={() => setExpanded(!expanded)}>
          <div className="flex-1">
            <p className="font-mono text-sm font-medium">{unit.sqlKey}</p>
            <p className="text-xs text-slate-500 mt-1">{unit.statementType} • {unit.namespace}</p>
          </div>
          <div className="flex items-center gap-2">
            <RiskBadge level={unit.riskLevel} flagCount={unit.riskFlags?.length} />
            <span className="text-xs text-slate-400">{unit.branchCount} branches</span>
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </div>
        </div>

        {expanded && (
          <div className="mt-4 space-y-2">
            <div className="p-2 bg-slate-50 rounded font-mono text-xs overflow-x-auto">
              <pre className="whitespace-pre-wrap">{unit.sql}</pre>
            </div>
            {unit.branches && unit.branches.length > 0 && (
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1">Branches:</p>
                {unit.branches.map((branch) => (
                  <div key={branch.id} className="p-2 bg-slate-50 rounded text-xs mb-1">
                    <span className="font-mono">#{branch.id}</span>
                    <span className="text-slate-400 ml-2">{branch.conditions?.join(', ')}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
