import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { GlassCard } from "@/components/ui/glass-card";

interface SkeletonCardProps {
  className?: string;
  lines?: number;
  hasIcon?: boolean;
}

export function SkeletonCard({ className, lines = 3, hasIcon = true }: SkeletonCardProps) {
  return (
    <GlassCard className={cn("space-y-4", className)}>
      <div className="flex items-center gap-3">
        {hasIcon && <Skeleton className="h-10 w-10 rounded-xl" />}
        <Skeleton className="h-5 w-24" />
      </div>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton 
          key={i} 
          className={cn("h-4", i === 0 ? "w-full" : i === 1 ? "w-3/4" : "w-1/2")} 
        />
      ))}
    </GlassCard>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <GlassCard className="space-y-4">
      <div className="flex justify-between items-center mb-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-9 w-28" />
      </div>
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 py-3">
            <Skeleton className="h-4 w-[30%]" />
            <Skeleton className="h-4 w-[20%]" />
            <Skeleton className="h-6 w-16 rounded-full" />
            <Skeleton className="h-4 w-[15%]" />
            <Skeleton className="h-6 w-20 rounded-full" />
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

export function SkeletonChart({ className }: { className?: string }) {
  return (
    <GlassCard className={cn("space-y-4", className)}>
      <Skeleton className="h-6 w-40" />
      <div className="flex items-end justify-around h-48 gap-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton 
            key={i} 
            className="w-12 rounded-t-lg"
            style={{ height: `${30 + Math.random() * 60}%` }}
          />
        ))}
      </div>
    </GlassCard>
  );
}
