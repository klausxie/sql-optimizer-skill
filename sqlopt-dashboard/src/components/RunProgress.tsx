import { Check } from 'lucide-react';
import { STAGE_ORDER } from '../types/v9';
import type { V9StageName } from '../types/v9';

interface RunProgressProps {
  completedStages: V9StageName[];
  currentStage: V9StageName | null;
  className?: string;
}

export function RunProgress({ completedStages, currentStage, className }: RunProgressProps) {
  return (
    <div className={`flex items-center gap-1 ${className ?? ''}`}>
      {STAGE_ORDER.map((stage, idx) => {
        const isCompleted = completedStages.includes(stage);
        const isCurrent = currentStage === stage && !isCompleted;
        return (
          <div key={stage} className="flex items-center">
            <div
              className={`
                w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium
                ${isCompleted ? 'bg-green-500 text-white' : isCurrent ? 'bg-blue-500 text-white animate-pulse' : 'bg-slate-200 text-slate-500'}
              `}
              title={stage}
            >
              {isCompleted ? <Check className="w-4 h-4" /> : idx + 1}
            </div>
            {idx < STAGE_ORDER.length - 1 && (
              <div className={`w-4 h-0.5 ${isCompleted ? 'bg-green-500' : 'bg-slate-200'}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
