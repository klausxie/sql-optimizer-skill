import { Badge } from './ui/badge';
import { AlertTriangle } from 'lucide-react';
import type { RiskLevel } from '../types/v9';

interface RiskBadgeProps {
  level: RiskLevel;
  flagCount?: number;
}

const variantMap: Record<RiskLevel, 'destructive' | 'secondary' | 'outline'> = {
  HIGH: 'destructive',
  MEDIUM: 'secondary',
  LOW: 'outline'
};

export function RiskBadge({ level, flagCount }: RiskBadgeProps) {
  return (
    <Badge variant={variantMap[level]} className="flex items-center gap-1">
      {level === 'HIGH' && <AlertTriangle className="w-3 h-3" />}
      {level}
      {flagCount !== undefined && flagCount > 0 && (
        <span className="ml-1 text-xs opacity-70">({flagCount})</span>
      )}
    </Badge>
  );
}
