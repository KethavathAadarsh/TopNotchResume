"use client";
import { useState } from "react";
import type { GenerateResponse } from "@/types/resume";
import { getDownloadUrl, generateCoverLetter } from "@/lib/api";
import { QualityCheckPanel } from "@/components/QualityCheckPanel";
import Link from "next/link";
import { useRouter } from "next/navigation";

interface Props {
  result: GenerateResponse;
  onRestart: () => void;
  selectedModel?: string;
}

function ScoreRing({ score }: { score: number }) {
  const color = score >= 80 ? "text-green-400" : score >= 60 ? "text-yellow-400" : "text-red-400";
  return (
    <div className={`text-5xl font-bold ${color}`}>
      {Math.round(score)}
      <span className="text-xl text-slate-500">/100</span>
    </div>
  );
}

function ScoreBar({ score }: { score: number }) {
  const color = score >= 80 ? "bg-green-500" : score >= 60 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="w-full h-1.5 bg-border rounded-full mt-3">
      <div className={`h-full rounded-full transition-all duration-700 ${color}`} style={{ width: `${score}%` }} />
    </div>
  );
}

export function DownloadStep({ result, onRestart, selectedModel }: Props) {
  const [currentResult, setCurrentResult] = useState<GenerateResponse>(result);
  const downloadUrl = getDownloadUrl(currentResult.download_id);
  const genSecs = (currentResult.generation_time_ms / 1000).toFixed(1);
  const router = useRouter();

  const [coverLetter, setCoverLetter] = useState("");
  const [subject, setSubject] = useState("");
  const [clLoading, setClLoading] = useState(false);
  const [clError, setClError] = useState("");
  const [copied, setCopied] = useState(false);

  async function handleGenerateCoverLetter() {
    setClLoading(true);
    setClError("");
    try {
      const res = await generateCoverLetter({
        download_id: result.download_id,
        composition: {},      // server reconstructs from download_id
        jd_analysis: {},
        optimized_content: {},
      });
      setCoverLetter(res.cover_letter);
      setSubject(res.subject_line);
    } catch (err: unknown) {
      setClError(err instanceof Error ? err.message : "Cover letter generation failed");
    } finally {
      setClLoading(false);
    }
  }

  async function handleCopy() {
    await navigator.clipboard.writeText(coverLetter);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="space-y-6 py-2">
      {/* Success header */}
      <div className="text-center">
        <div className="text-4xl mb-3">✅</div>
        <h3 className="text-xl font-bold text-white mb-1">Your resume is ready</h3>
        <p className="text-sm text-slate-500">Generated in {genSecs}s by JARVIS v2</p>
      </div>

      {/* ATS Score */}
      <div className="card p-6 text-center">
        <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">ATS Compatibility Score</p>
        <ScoreRing score={currentResult.ats_score} />
        <ScoreBar score={currentResult.ats_score} />
        <p className="text-xs text-slate-500 mt-3">
          {currentResult.ats_score >= 80 ? "Excellent — this resume will pass most ATS systems." :
           currentResult.ats_score >= 60 ? "Good — consider adding more keywords from the JD." :
           "Fair — review the missing keywords below."}
        </p>
      </div>

      {/* Keywords */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {currentResult.keywords_matched.length > 0 && (
          <div className="card p-4">
            <p className="text-xs text-green-400 font-medium uppercase tracking-wide mb-3">
              ✓ Matched ({currentResult.keywords_matched.length})
            </p>
            <div className="flex flex-wrap gap-1.5">
              {currentResult.keywords_matched.slice(0, 20).map(kw => (
                <span key={kw} className="text-xs bg-green-500/10 border border-green-500/20 text-green-400 rounded-full px-2.5 py-0.5">
                  {kw}
                </span>
              ))}
            </div>
          </div>
        )}
        {currentResult.keywords_missing.length > 0 && (
          <div className="card p-4">
            <p className="text-xs text-yellow-400 font-medium uppercase tracking-wide mb-3">
              ⚠ Missing ({currentResult.keywords_missing.length})
            </p>
            <div className="flex flex-wrap gap-1.5">
              {currentResult.keywords_missing.slice(0, 15).map(kw => (
                <span key={kw} className="text-xs bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 rounded-full px-2.5 py-0.5">
                  {kw}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Sections */}
      <div className="card p-4">
        <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-3">Sections Included</p>
        <div className="flex flex-wrap gap-2">
          {currentResult.sections_included.map(s => (
            <span key={s} className="text-xs bg-brand-500/10 border border-brand-500/20 text-brand-400 rounded-full px-3 py-1 capitalize">
              {s}
            </span>
          ))}
        </div>
      </div>

      {/* Download + Enhance */}
      <div className="flex flex-col gap-3">
        <a href={downloadUrl} download className="btn-primary text-center text-base py-3 block">
          ↓ Download Resume (.docx)
        </a>
        {currentResult.session_id && (
          <button
            onClick={() => router.push(`/enhance?id=${currentResult.session_id}`)}
            className="btn-secondary text-sm py-2.5 flex items-center justify-center gap-2"
          >
            <span>Enhance Resume</span>
            <span className="text-brand-400">✨</span>
            <span className="text-xs text-slate-500 ml-1">RSEA — gap analysis + AI refinement</span>
          </button>
        )}
      </div>

      {/* Quality Check & Iterative Refinement */}
      <QualityCheckPanel
        downloadId={currentResult.download_id}
        onRefineComplete={(refined) => setCurrentResult(refined)}
        selectedModel={selectedModel}
      />

      {/* Cover Letter Section */}
      <div className="card p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-white">Cover Letter Generator</p>
            <p className="text-xs text-slate-500 mt-0.5">AI-written, tailored to the same job</p>
          </div>
          {!coverLetter && (
            <button
              onClick={handleGenerateCoverLetter}
              disabled={clLoading}
              className="btn-secondary text-xs px-4 py-2 disabled:opacity-50"
            >
              {clLoading ? "Writing…" : "Generate ✨"}
            </button>
          )}
        </div>

        {clError && <p className="text-xs text-red-400">{clError}</p>}

        {coverLetter && (
          <div className="space-y-3">
            {subject && (
              <div className="bg-brand-500/5 border border-brand-500/20 rounded px-3 py-2">
                <p className="text-xs text-slate-500">Subject line</p>
                <p className="text-sm text-white mt-0.5">{subject}</p>
              </div>
            )}
            <div className="relative">
              <textarea
                readOnly
                value={coverLetter}
                rows={10}
                className="w-full bg-surface border border-border rounded-lg px-4 py-3 text-sm text-slate-300 leading-relaxed resize-none font-mono"
              />
              <button
                onClick={handleCopy}
                className="absolute top-2 right-2 text-xs bg-border hover:bg-brand-500/20 text-slate-400 hover:text-brand-400 rounded px-2.5 py-1 transition-colors"
              >
                {copied ? "Copied ✓" : "Copy"}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-3">
        <button onClick={onRestart} className="btn-secondary text-sm py-2.5">
          Generate Another Resume
        </button>
        <div className="flex items-center justify-between text-xs text-slate-600">
          <Link href="/history" className="hover:text-slate-400 transition-colors">
            View history →
          </Link>
          <Link href="/" className="hover:text-slate-400 transition-colors">
            ← Home
          </Link>
        </div>
      </div>

      <p className="text-xs text-center text-slate-700">
        Download link expires in 24 hours. Open in Word, Google Docs, or any .docx viewer.
      </p>
    </div>
  );
}
