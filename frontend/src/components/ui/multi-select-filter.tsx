// frontend/src/components/ui/multi-select-filter.tsx
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface MultiSelectOption {
  value: string;
  label: string;
}

interface MultiSelectFilterProps {
  label: string;
  options: MultiSelectOption[];
  selected: string[];
  onChange: (values: string[]) => void;
  className?: string;
  /** Localized label for the dropdown clear action. Defaults to "Clear". */
  clearLabel?: string;
  /**
   * Override the "active" visual state of the trigger button.
   * When omitted the component falls back to `selected.length > 0`.
   * Pass `false` to suppress highlighting even when items are selected
   * (e.g. when the current selection matches a baseline preset).
   */
  isActive?: boolean;
}

export function MultiSelectFilter({
  label,
  options,
  selected,
  onChange,
  className,
  clearLabel,
  isActive: isActiveOverride,
}: MultiSelectFilterProps) {
  const hasSelection = selected.length > 0;
  const isActive = isActiveOverride ?? hasSelection;

  const toggle = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value));
    } else {
      onChange([...selected, value]);
    }
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={cn(
            "h-8 text-sm glass border-border/50 gap-1.5",
            isActive && "border-primary/50 bg-primary/10 text-primary",
            className
          )}
        >
          <span>{label}</span>
          {hasSelection && (
            <span className="flex items-center justify-center h-4 min-w-4 px-1 rounded-full bg-primary text-primary-foreground text-[10px] font-bold leading-none">
              {selected.length}
            </span>
          )}
          <ChevronDown className="h-3 w-3 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-48 p-2" align="start">
        <div className="space-y-1">
          {options.map((option) => {
            const checked = selected.includes(option.value);
            return (
              <label
                key={option.value}
                className="flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer hover:bg-muted/50 text-sm"
              >
                <Checkbox
                  checked={checked}
                  onCheckedChange={() => toggle(option.value)}
                  className="shrink-0"
                />
                <span>{option.label}</span>
              </label>
            );
          })}
        </div>
        {hasSelection && (
          <>
            <div className="my-1.5 border-t border-border/50" />
            <button
              onClick={() => onChange([])}
              className="w-full text-xs text-muted-foreground hover:text-foreground px-2 py-1 text-left rounded-md hover:bg-muted/50"
            >
              {clearLabel ?? "Clear"}
            </button>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}
