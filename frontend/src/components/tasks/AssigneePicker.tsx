import { useState } from 'react';
import { ChevronDown, Check, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { useTaskAssigneeRecommendations } from '@/hooks/useTasks';
import { useLanguage } from '@/i18n/LanguageContext';
import type { AssigneeRecommendation } from '@/types';

interface AssigneePickerProps {
  /** Current assignee ID, or empty string for unassigned. */
  value: string;
  onChange: (value: string) => void;
  people: { id: string; name: string }[];
  /**
   * When provided, AI recommendations are fetched for this task and shown
   * above the full people list. Omit (or pass null/undefined) when no task
   * exists yet (e.g. create form).
   */
  taskId?: string | null;
}

function confidenceBadgeClass(score: number) {
  if (score >= 0.8) return 'bg-success/10 text-success border-success/30';
  if (score >= 0.5) return 'bg-warning/10 text-warning border-warning/30';
  return 'bg-destructive/10 text-destructive border-destructive/30';
}

function policyFlagClass(flag: string) {
  if (flag.includes('risk')) return 'bg-warning/10 text-warning';
  if (flag.includes('expert') || flag.includes('strong')) return 'bg-success/10 text-success';
  return 'bg-muted text-muted-foreground';
}

export function AssigneePicker({ value, onChange, people, taskId }: AssigneePickerProps) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);

  const { data: recommendationsData, isLoading: isLoadingRecommendations } =
    useTaskAssigneeRecommendations(taskId ?? null);

  const recommendations = recommendationsData?.recommendations ?? [];
  const recommendedPersonIds = new Set(
    recommendations
      .map((r: AssigneeRecommendation) => r.person_id)
      .filter((id: string | null): id is string => id != null),
  );

  const otherPeople = people
    .filter((p) => !recommendedPersonIds.has(p.id))
    .sort((a, b) => a.name.localeCompare(b.name));

  const displayName = value
    ? (people.find((p) => p.id === value)?.name ?? t.taskModal.unassigned)
    : t.taskModal.unassigned;

  function handleSelect(personId: string) {
    onChange(personId);
    setOpen(false);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="flex w-full items-center justify-between gap-2 rounded-xl border border-border bg-background px-3 py-2 text-left text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
        >
          <span className="truncate">{displayName}</span>
          {isLoadingRecommendations && taskId ? (
            <Loader2 className="h-3.5 w-3.5 flex-shrink-0 animate-spin text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
          )}
        </button>
      </PopoverTrigger>

      <PopoverContent
        align="start"
        // Stop Escape from bubbling to parent modal handlers; Radix closes the
        // popover first, a second Escape then closes the modal (standard UX).
        onEscapeKeyDown={(e) => e.stopPropagation()}
        className="max-h-80 w-auto max-w-80 overflow-y-auto rounded-xl border-border bg-popover p-0 text-popover-foreground shadow-xl"
        style={{ minWidth: 'var(--radix-popover-trigger-width)' }}
      >
        {isLoadingRecommendations && taskId ? (
          <div className="p-4 text-center text-xs text-muted-foreground">
            <Loader2 className="mx-auto mb-2 h-4 w-4 animate-spin" />
            {t.taskModal.loadingRecommendations}
          </div>
        ) : (
          <>
            {recommendations.length > 0 && (
              <div className="p-2">
                <p className="mb-1.5 px-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                  {t.taskModal.aiRecommendations}
                </p>
                <div className="space-y-1.5">
                  {recommendations.map((rec: AssigneeRecommendation) => (
                    <button
                      key={rec.person_id ?? rec.name}
                      type="button"
                      onClick={() => handleSelect(rec.person_id ?? '')}
                      className={cn(
                        'w-full rounded-lg border p-2 text-left transition-colors',
                        value === rec.person_id
                          ? 'border-primary bg-primary/5'
                          : 'border-border bg-muted/30 hover:bg-accent',
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <span className="text-[10px] font-bold text-muted-foreground flex-shrink-0">
                            #{rec.rank}
                          </span>
                          <span className="truncate text-xs font-bold text-foreground">
                            {rec.name}
                          </span>
                          <span
                            className={cn(
                              'flex-shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-bold',
                              confidenceBadgeClass(rec.confidence_score),
                            )}
                          >
                            {Math.round(rec.confidence_score * 100)}%
                          </span>
                        </div>
                        {value === rec.person_id && (
                          <Check className="w-3.5 h-3.5 text-primary flex-shrink-0" />
                        )}
                      </div>
                      <p className="mt-1 line-clamp-2 text-[11px] text-muted-foreground">
                        {rec.reasoning}
                      </p>
                      {rec.policy_flags && rec.policy_flags.length > 0 && (
                        <div className="flex gap-1 mt-1.5 flex-wrap">
                          {rec.policy_flags.slice(0, 2).map((flag) => (
                            <span
                              key={flag}
                              className={cn(
                                'rounded px-1.5 py-0.5 text-[10px] font-medium',
                                policyFlagClass(flag),
                              )}
                            >
                              {flag.replace(/_/g, ' ')}
                            </span>
                          ))}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className={cn('p-2', recommendations.length > 0 && 'border-t border-border')}>
              <p className="mb-1.5 px-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                {t.taskModal.allPeople}
              </p>
              <button
                type="button"
                onClick={() => handleSelect('')}
                className={cn(
                  'w-full rounded-lg px-2.5 py-1.5 text-sm text-left transition-colors flex items-center justify-between',
                  !value
                    ? 'bg-primary/5 text-primary font-semibold'
                    : 'text-foreground hover:bg-accent',
                )}
              >
                <span>{t.taskModal.unassigned}</span>
                {!value && <Check className="w-3.5 h-3.5" />}
              </button>
              {otherPeople.map((person) => (
                <button
                  key={person.id}
                  type="button"
                  onClick={() => handleSelect(person.id)}
                  className={cn(
                    'w-full rounded-lg px-2.5 py-1.5 text-sm text-left transition-colors flex items-center justify-between',
                    value === person.id
                      ? 'bg-primary/5 text-primary font-semibold'
                      : 'text-foreground hover:bg-accent',
                  )}
                >
                  <span className="truncate">{person.name}</span>
                  {value === person.id && <Check className="w-3.5 h-3.5 flex-shrink-0" />}
                </button>
              ))}
            </div>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}
