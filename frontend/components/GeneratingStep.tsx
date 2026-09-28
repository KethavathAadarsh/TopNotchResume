"use client";
import { useEffect, useRef, useState, useCallback } from "react";

const STEPS = [
  { key: "parallel_init", label: "Intelligence Init",  desc: "Profile + JD agents running in parallel" },
  { key: "relevance",     label: "Relevance Engine",   desc: "Semantic alignment score + experience ranking" },
  { key: "optimize",      label: "Content Optimizer",  desc: "Rewriting bullets for impact and ATS keywords" },
  { key: "compose",       label: "Composer Agent",     desc: "Section order, bullet density, page-fit" },
  { key: "render",        label: "DOCX Engine",        desc: "Rendering polished document with format theme" },
];

const ALL_STEP_KEYS = new Set(STEPS.map(s => s.key));

interface SSEEvent {
  step: string;
  status: string;
  label?: string;
  result?: Record<string, unknown>;
  error?: string;
}

interface Props {
  jobId?: string;
  error?: string;
  onComplete?: (result: Record<string, unknown>) => void;
  onError?: (msg: string) => void;
}

export function GeneratingStep({ jobId, error, onComplete, onError }: Props) {
  const [doneSteps, setDoneSteps] = useState<Set<string>>(new Set());
  const [activeStep, setActiveStep] = useState<string>("parallel_init");
  const [elapsed, setElapsed] = useState(0);
  const [liveError, setLiveError] = useState("");
  const [recovering, setRecovering] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const completedRef = useRef(false);

  useEffect(() => {
    const t = setInterval(() => setElapsed(s => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  // Fetch result directly from REST endpoint — used as SSE fallback so we never
  // depend on the fragile SSE "complete" event reaching the browser.
  // Returns true once the job reached a terminal state (done or error).
  const fetchResult = useCallback(async (jId: string): Promise<boolean> => {
    if (completedRef.current) return true;
    const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    try {
      const res = await fetch(`${API}/api/generate/result/${jId}`);
      if (!res.ok) return false;
      const data = await res.json();
      if (data.status === "done" && data.result && !completedRef.current) {
        completedRef.current = true;
        esRef.current?.close();
        setDoneSteps(new Set(STEPS.map(s => s.key)));
        onComplete?.(data.result);
        return true;
      }
      if (data.status === "error" && !completedRef.current) {
        completedRef.current = true;
        esRef.current?.close();
        onError?.(data.error || "Pipeline error");
        return true;
      }
    } catch {
      // silent — the poll loop will retry
    }
    return false;
  }, [onComplete, onError]);

  // The job keeps running server-side even if the SSE stream drops, so the
  // result endpoint — not the stream — is the source of truth for completion.
  // Poll it before ever telling the user the generation failed.
  const pollUntilDone = useCallback(async (jId: string, reason: string) => {
    const DEADLINE_MS = 15 * 60_000;
    const INTERVAL_MS = 3_000;
    const started = Date.now();

    setRecovering(true);
    while (!completedRef.current && Date.now() - started < DEADLINE_MS) {
      if (await fetchResult(jId)) {
        setRecovering(false);
        return;
      }
      await new Promise(r => setTimeout(r, INTERVAL_MS));
    }
    setRecovering(false);

    if (!completedRef.current) {
      completedRef.current = true;
      const msg = `${reason} and the job did not finish within 15 minutes.`;
      setLiveError(msg);
      onError?.(msg);
    }
  }, [fetchResult, onError]);

  useEffect(() => {
    if (!jobId) {
      let idx = 0;
      const t = setInterval(() => {
        idx = Math.min(idx + 1, STEPS.length - 1);
        setActiveStep(STEPS[idx].key);
      }, 3800);
      return () => clearInterval(t);
    }

    completedRef.current = false;
    const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const es = new EventSource(`${API}/api/generate/stream/${jobId}`);
    esRef.current = es;

    es.onmessage = (ev) => {
      if (completedRef.current) return;
      try {
        const data: SSEEvent = JSON.parse(ev.data);

        // "complete" check must precede "status === done" — the complete event
        // also has status:"done" which would match the wrong branch otherwise.
        if (data.step === "complete" && data.result) {
          completedRef.current = true;
          es.close();
          setDoneSteps(new Set(STEPS.map(s => s.key)));
          onComplete?.(data.result);
        } else if (data.step === "stream_timeout") {
          // Server closed the stream but the pipeline is still running.
          es.close();
          void pollUntilDone(jobId, "The live progress stream timed out");
        } else if (data.step === "error" || data.error) {
          // Confirm against the result endpoint before failing — the pipeline
          // may still be running or may have already succeeded.
          es.close();
          void pollUntilDone(jobId, data.error || "Pipeline error");
        } else if (data.status === "running") {
          setActiveStep(data.step);
        } else if (data.status === "done") {
          setDoneSteps(prev => {
            const next = new Set([...Array.from(prev), data.step]);
            // All pipeline steps done → fetch result via HTTP (belt-and-suspenders)
            if (ALL_STEP_KEYS.size > 0 && [...ALL_STEP_KEYS].every(k => next.has(k))) {
              setTimeout(() => fetchResult(jobId), 500);
            }
            return next;
          });
          const idx = STEPS.findIndex(s => s.key === data.step);
          if (idx >= 0 && idx < STEPS.length - 1) setActiveStep(STEPS[idx + 1].key);
        }
      } catch {
        // ignore malformed frames
      }
    };

    es.onerror = () => {
      if (completedRef.current) return;
      // Don't fail here — the pipeline may still be running, or may have
      // finished with the SSE close racing the complete event. Poll instead.
      es.close();
      void pollUntilDone(jobId, "Lost connection to the generation server");
    };

    return () => { es.close(); };
  }, [jobId, onComplete, onError, fetchResult, pollUntilDone]);

  const displayError = error || liveError;

  if (displayError) {
    return (
      <div className="text-center space-y-4 py-8">
        <div className="text-4xl">❌</div>
        <h3 className="text-lg font-semibold text-white">Generation Failed</h3>
        <p className="text-sm text-red-400 max-w-md mx-auto">{displayError}</p>
        <p className="text-xs text-slate-500">
          Your input is still filled in — go back and retry without re-entering anything.
          If this repeats, check that ANTHROPIC_API_KEY is set in backend/.env.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 py-4">
      <div className="text-center">
        <div className="inline-flex items-center gap-2 mb-4">
          <div className="w-2 h-2 rounded-full bg-brand-500 animate-pulse" />
          <span className="text-sm font-medium text-brand-400">JARVIS is working</span>
          <div className="w-2 h-2 rounded-full bg-brand-500 animate-pulse" style={{ animationDelay: "0.3s" }} />
        </div>
        <p className="text-xs text-slate-500">
          {elapsed}s elapsed — usually 60–180s (longer for profiles with many roles or projects)
        </p>
        {jobId && (
          <p className="text-xs text-slate-600 mt-1">
            {recovering
              ? "Progress stream dropped — still generating, checking for your result…"
              : "Live pipeline stream active"}
          </p>
        )}
      </div>

      <div className="space-y-3">
        {STEPS.map((step) => {
          const isDone = doneSteps.has(step.key);
          const isActive = !isDone && step.key === activeStep;

          return (
            <div
              key={step.key}
              className={`card p-3.5 flex items-center gap-3.5 transition-all duration-300 ${
                isActive ? "border-brand-500/50 bg-brand-500/5" :
                isDone   ? "opacity-70" : "opacity-25"
              }`}
            >
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs shrink-0 ${
                isDone   ? "bg-green-500/20 text-green-400 border border-green-500/30" :
                isActive ? "bg-brand-500/20 text-brand-400 border border-brand-500/40" :
                           "bg-border text-slate-600 border border-border"
              }`}>
                {isDone   ? "✓" :
                 isActive ? <span className="animate-spin inline-block">◌</span> :
                            <span className="text-[10px]">{STEPS.indexOf(step) + 1}</span>}
              </div>
              <div>
                <p className="text-sm font-medium text-white">{step.label}</p>
                {isActive && <p className="text-xs text-slate-500 mt-0.5">{step.desc}</p>}
                {isDone   && <p className="text-xs text-green-500/70 mt-0.5">Complete</p>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
