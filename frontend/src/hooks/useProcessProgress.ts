import { useState, useCallback, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/hooks/useToast";

export interface ProgressEvent {
  step: string;
  message: string;
  progress: number;
  status: "processing" | "done" | "error" | "ignored";
  data?: {
    status?: string;
    old_assignment_id?: string | null;
    new_assignment_id?: string | null;
    email_id?: string;
  };
}

export interface ProcessingState {
  /** The assignment/email ID currently being processed */
  activeId: string | null;
  /** Whether processing is in progress */
  isProcessing: boolean;
  /** Current progress event */
  currentEvent: ProgressEvent | null;
  /** History of all events for this processing run */
  events: ProgressEvent[];
}

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8008/api";

/**
 * Hook to process an email with SSE-based progress tracking.
 * Uses the /assignments/{id}/process-stream endpoint.
 */
export function useProcessEmailWithProgress() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const abortRef = useRef<AbortController | null>(null);

  const [state, setState] = useState<ProcessingState>({
    activeId: null,
    isProcessing: false,
    currentEvent: null,
    events: [],
  });

  const processEmail = useCallback(
    async (assignmentId: string) => {
      // Abort any previous stream
      if (abortRef.current) {
        abortRef.current.abort();
      }

      const controller = new AbortController();
      abortRef.current = controller;

      setState({
        activeId: assignmentId,
        isProcessing: true,
        currentEvent: { step: "loading", message: "Starting...", progress: 0, status: "processing" },
        events: [],
      });

      try {
        const response = await fetch(
          `${API_URL}/assignments/${assignmentId}/process-stream`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            signal: controller.signal,
          }
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse SSE events from buffer
          const lines = buffer.split("\n");
          buffer = lines.pop() || ""; // Keep incomplete line in buffer

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data: ")) continue;

            try {
              const event: ProgressEvent = JSON.parse(trimmed.slice(6));

              setState((prev) => ({
                ...prev,
                currentEvent: event,
                events: [...prev.events, event],
              }));

              // Handle terminal states
              if (event.status === "done") {
                setState((prev) => ({ ...prev, isProcessing: false }));
                queryClient.invalidateQueries({ queryKey: ["assignments"] });
                queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
                queryClient.invalidateQueries({ queryKey: ["employees"] });
                toast({
                  title: "Email Processed",
                  description: "Email analyzed and assigned successfully",
                });
              } else if (event.status === "error") {
                setState((prev) => ({ ...prev, isProcessing: false }));
                toast({
                  title: "Processing Failed",
                  description: event.message,
                  variant: "destructive",
                });
              } else if (event.status === "ignored") {
                setState((prev) => ({ ...prev, isProcessing: false }));
                queryClient.invalidateQueries({ queryKey: ["assignments"] });
                toast({
                  title: "Email Ignored",
                  description: event.message,
                });
              }
            } catch {
              // Skip malformed events
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") return;

        const message = err instanceof Error ? err.message : "Unknown error";
        setState((prev) => ({
          ...prev,
          isProcessing: false,
          currentEvent: {
            step: "error",
            message,
            progress: 1,
            status: "error",
          },
        }));
        toast({
          title: "Processing Failed",
          description: message,
          variant: "destructive",
        });
      }
    },
    [queryClient, toast]
  );

  const dismiss = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
    setState({
      activeId: null,
      isProcessing: false,
      currentEvent: null,
      events: [],
    });
  }, []);

  return { ...state, processEmail, dismiss };
}
