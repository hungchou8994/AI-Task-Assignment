import { AlertCircle, TrendingUp, TrendingDown } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StatCardProps {
  title: string;
  value: string | number;
  trend?: 'up' | 'down';
  trendValue?: string;
  alert?: boolean;
}

export function StatCard({ title, value, trend, trendValue, alert }: StatCardProps) {
  return (
    <div className="bg-card border border-border p-5 relative overflow-hidden">
      {alert && (
        <div className="absolute top-0 right-0 p-3">
          <AlertCircle className="w-4 h-4 text-warning" />
        </div>
      )}
      <p className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground font-mono">
        {title}
      </p>
      <div className="flex items-end justify-between mt-2">
        <p className={cn('text-2xl font-bold text-foreground tabular-nums', alert && 'text-warning')}>
          {value}
        </p>
        {trend && (
          <span
            className={cn(
              'text-xs font-bold flex items-center gap-1',
              trend === 'up' ? 'text-success' : 'text-destructive',
            )}
          >
            {trend === 'up' ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
            {trendValue}
          </span>
        )}
        {alert && (
          <span className="text-[10px] font-bold uppercase tracking-widest text-warning">
            Alert
          </span>
        )}
      </div>
    </div>
  );
}
