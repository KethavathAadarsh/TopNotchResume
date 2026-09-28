"use client";
import { useEffect, useRef, useState } from "react";
import { runQualityCheck, startRefine, type QualityReport } from "@/lib/api";
import { GeneratingStep } from "@/components/GeneratingStep";
import type { GenerateResponse } from "@/types/resume";

interface Props {
  downloadId: string;
  onRefineComplete: (newResult: GenerateResponse) => void;
  selectedModel?: string;
}

type PanelState = "checking" | "report" | "starting" | "generating" | "satisfied";

const MAX_ITERATIONS = 10;

export function QualityCheckPanel({ downloadId, onRefineComplete, selectedModel }: Props) {
  const [panelState, setPanelState] = useState<PanelState>("checking");
  const [report, setReport] = useState<QualityReport | null>(null);
  const [checkError, setCheckError] = useState("");
  const [userFeedback, setUserFeedback] = useState("");
  const [iteration, setIteration] = useState(1);
  const [refineJobId, setRefineJobId] = useState("");
  const [refineError, setRefineError] = useState("");
  const iterationRef = useRef(1);

  // Auto-run quality check whenever downloadId changes (initial mount + after each refine)
  useEffect(() => {
    let cancelled = false;
    setPanelState("checking");
    setCheckError("");
    setReport(null);

    runQualityCheck({
      download_id: downloadId,
      user_feedback: "",
      iteration: iterationRef.current,
    })
      .then((r) => {
        if (!cancelled) {
          setReport(r);
          setPanelState("report");
        }
      })
      .catch((e: Error) => {
        if (!cancelled) {
          setCheckError(e.message || "Quality check failed");
          setPanelState("report");
        }
      });

    return () => { cancelled = true; };
  }, [downloadId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleRefine() {
    if (iterationRef.current >= MAX_ITERATIONS) return;
    setPanelState("starting");
    setRefineError("");

    try {
      const res = await startRefine({
        download_id: downloadId,
        user_feedback: userFeedback,
        iteration: iterationRef.current,
        model: selectedModel,
      });
      if (res.quality_report) setReport(res.quality_report);
      setRefineJobId(res.job_id);
      setPanelState("generating");
    } catch (e: unknown) {
      setRefineError(e instanceof Error ? e.message : "Refine request failed");
      setPanelState("report");
    }
  }

  function handleSSEComplete(raw: Record<string, unknown>) {
    const newResult: GenerateResponse = {
      download_id: raw.download_id as string,
      session_id: raw.session_id as string | undefined,
      ats_score: raw.ats_score as number,
      keywords_matched: raw.keywords_matched as string[],
      keywords_missing: raw.keywords_missing as string[],
      sections_included: raw.sections_included as string[],
      generation_time_ms: raw.generation_time_ms as number,
    };
    iterationRef.current += 1;
    setIteration(iterationRef.current);
    setUserFeedback("");
    setRefineJobId("");
    onRefineComplete(newResult);
    // useEffect above will auto-re-run quality check when downloadId changes
  }

  function handleSSEError(msg: string) {
    setRefineError(msg);
    setRefineJobId("");
    setPanelState("report");
  }

  if (panelState === "satisfied") {
    return (
      <div className="card p-4 flex items-center justify-center gap-3 text-green-400 text-sm">
        <span className="text-lg">✅</span>
        <span>You're satisfied with this resume — good luck with your application!</span>
      </div>
    );
  }

  const scoreColor =
    !report ? ""
    : report.quality_score >= 85 ? "text-green-400"
    : report.quality_score >= 65 ? "text-yellow-400"
    : "text-red-400";

  const barColor =
    !report ? "bg-border"
    : report.quality_score >= 85 ? "bg-green-500"
    : report.quality_score >= 65 ? "bg-yellow-500"
    : "bg-red-500";

  return (
    <div className="card p-5 space-y-4 border-brand-500/20">

      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-white flex items-center gap-2">
            🔍 Quality Intelligence Check
            <span className="text-xs text-slate-500 font-normal">
              Iteration {iteration} / {MAX_ITERATIONS}
            </span>
          </p>
          <p className="text-xs text-slate-500 mt-0.5">
            Agent validates all 7 sections against your profile — auto-fixes missing content
          </p>
        </div>
        {panelState === "report" && !checkError && (
          <button
            onClick={() => setPanelState("satisfied")}
            className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors flex-shrink-0"
          >
            ✓ I'm Satisfied
          </button>
        )}
      </div>

      {/* ── Checking spinner ── */}
      {panelState === "checking" && (
        <div className="flex items-center gap-3 py-3">
          <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin flex-shrink-0" />
          <p className="text-sm text-slate-400">
            Validating resume completeness against your 7 sections…
          </p>
        </div>
      )}

      {/* ── Starting refine ── */}
      {panelState === "starting" && (
        <div className="flex items-center gap-3 py-3">
          <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin flex-shrink-0" />
          <p className="text-sm text-slate-400">Submitting refinement job…</p>
        </div>
      )}

      {/* ── Generating (SSE stream) ── */}
      {panelState === "generating" && refineJobId && (
        <div className="space-y-2">
          <p className="text-xs text-brand-400 font-medium">
            Refining resume — applying quality fixes (iteration {iteration + 1})…
          </p>
          <GeneratingStep
            jobId={refineJobId}
            onComplete={handleSSEComplete}
            onError={handleSSEError}
          />
        </div>
      )}

      {/* ── Quality report ── */}
      {panelState === "report" && (
        <>
          {/* Check failed (old generation without persistence) */}
          {checkError && !report && (
            <div className="bg-yellow-500/5 border border-yellow-500/20 rounded-lg p-3 text-xs text-yellow-400">
              {checkError.includes("before persistence")
                ? "Quality check is available for resumes generated after persistence was enabled. Generate a new resume to use this feature."
                : checkError}
            </div>
          )}

          {report && (
            <div className="space-y-4">
              {/* Score + bar */}
              <div className="flex items-center gap-4">
                <div className={`text-3xl font-bold ${scoreColor}`}>
                  {report.quality_score}
                  <span className="text-base text-slate-500">/100</span>
                </div>
                <div className="flex-1">
                  <p className="text-xs text-slate-400">
                    {report.satisfied
                      ? "✅ All content verified — nothing missing"
                      : report.quality_score >= 65
                      ? "⚠️ Some improvements detected"
                      : "❌ Missing or truncated content found"}
                  </p>
                  <div className="w-full h-1.5 bg-border rounded-full mt-2">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${barColor}`}
                      style={{ width: `${report.quality_score}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Issues */}
              {report.issues.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">
                    Issues Found ({report.issues.length})
                  </p>
                  {report.issues.map((issue, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <span className="text-red-400 text-xs mt-0.5 flex-shrink-0">✗</span>
                      <p className="text-xs text-slate-300">{issue}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Recommendations */}
              {!report.satisfied && report.recommendations.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">
                    Agent Recommendations
                  </p>
                  {report.recommendations.map((rec, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <span className="text-brand-400 text-xs mt-0.5 flex-shrink-0">→</span>
                      <p className="text-xs text-slate-300">{rec}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Satisfied banner */}
              {report.satisfied && (
                <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-3 text-xs text-green-400">
                  ✅ Resume quality is excellent — all sections verified and complete.
                </div>
              )}

              {/* HITL + Refine button */}
              {!report.satisfied && iteration < MAX_ITERATIONS && (
                <div className="space-y-3 pt-2 border-t border-border">
                  <div>
                    <label className="text-xs text-slate-400 font-medium block mb-1.5">
                      Human-in-the-loop instructions{" "}
                      <span className="text-slate-600 font-normal">(optional)</span>
                    </label>
                    <textarea
                      value={userFeedback}
                      onChange={(e) => setUserFeedback(e.target.value)}
                      rows={2}
                      placeholder='e.g. "Make sure all 3 AWS certifications appear" or "Emphasise the ML experience more"'
                      className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-slate-300 placeholder-slate-600 resize-none focus:outline-none focus:border-brand-500/50 transition-colors"
                    />
                  </div>
                  {refineError && (
                    <p className="text-xs text-red-400">{refineError}</p>
                  )}
                  <button
                    onClick={handleRefine}
                    className="btn-primary text-sm w-full py-2.5 flex items-center justify-center gap-2"
                  >
                    <span>⚙️ Refine Resume</span>
                    {report.issues.length > 0 && (
                      <span className="text-xs opacity-75">
                        — fix {report.issues.length} issue{report.issues.length !== 1 ? "s" : ""}
                      </span>
                    )}
                  </button>
                </div>
              )}

              {/* Max iterations */}
              {iteration >= MAX_ITERATIONS && !report.satisfied && (
                <div className="text-xs text-slate-500 text-center py-1">
                  Max refinement passes reached. Use{" "}
                  <span className="text-brand-400">✨ Enhance (RSEA)</span> for deeper AI improvements.
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
