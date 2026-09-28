"use client";
import type { ResumeFormat } from "@/types/resume";
import { RESUME_FORMAT_LABELS } from "@/types/resume";

interface Props {
  format: ResumeFormat;
  maxPages: 1 | 2;
  onChangeFormat: (f: ResumeFormat) => void;
  onChangePages: (p: 1 | 2) => void;
}

const FORMAT_DESCRIPTIONS: Record<ResumeFormat, string> = {
  ats: "Maximum ATS compatibility. Standard section names, keyword density optimized.",
  executive: "Senior leadership tone. Emphasizes business impact, team scale, P&L.",
  swe: "Technical depth. Systems design language, architecture patterns, scale metrics.",
  startup: "Scrappy, high-velocity tone. Ownership, shipping speed, cross-functional.",
  minimal: "Clean, sparse layout. Lets achievements speak without clutter.",
  research: "Academic tone. Publications, methodologies, research contributions.",
};

export function OutputOptionsStep({ format, maxPages, onChangeFormat, onChangePages }: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white mb-1">Output Options</h2>
        <p className="text-sm text-slate-500">Configure the final resume format and length.</p>
      </div>

      {/* Page count */}
      <div>
        <label className="label-base">Resume Length</label>
        <div className="grid grid-cols-2 gap-3 mt-2">
          {([1, 2] as const).map(pages => (
            <button
              key={pages}
              onClick={() => onChangePages(pages)}
              className={`card p-4 text-center border-2 transition-colors duration-150 ${
                maxPages === pages ? "border-brand-500 bg-brand-500/10" : "border-transparent hover:border-border"
              }`}
            >
              <p className="text-2xl font-bold text-white mb-1">{pages}</p>
              <p className="text-xs text-slate-400">{pages === 1 ? "Page — Recommended" : "Pages — Senior roles"}</p>
              <p className="text-xs text-slate-600 mt-1">
                {pages === 1 ? "Ruthless prioritization. Ideal for most roles." : "More comprehensive. Best for 10+ years experience."}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Format */}
      <div>
        <label className="label-base">Resume Style</label>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-2">
          {(Object.keys(RESUME_FORMAT_LABELS) as ResumeFormat[]).map(f => (
            <button
              key={f}
              onClick={() => onChangeFormat(f)}
              className={`card p-3 text-left border-2 transition-colors duration-150 ${
                format === f ? "border-brand-500 bg-brand-500/10" : "border-transparent hover:border-border"
              }`}
            >
              <p className="text-sm font-semibold text-white mb-1">{RESUME_FORMAT_LABELS[f]}</p>
              <p className="text-xs text-slate-500 leading-relaxed">{FORMAT_DESCRIPTIONS[f]}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Summary */}
      <div className="bg-brand-500/5 border border-brand-500/20 rounded-xl p-4 space-y-2">
        <p className="text-sm font-medium text-brand-400">JARVIS will generate:</p>
        <ul className="text-xs text-slate-400 space-y-1.5">
          <li>• Tailored professional summary targeting the specific role</li>
          <li>• High-impact bullet rewrites using quantified impact + action verbs</li>
          <li>• ATS keyword injection and density optimization</li>
          <li>• Optimal section ordering for {RESUME_FORMAT_LABELS[format]} format</li>
          <li>• {maxPages === 1 ? "Intelligent 1-page fit — most relevant content surfaced" : "Comprehensive 2-page layout with full experience"}</li>
          <li>• Professional .docx with clean typography</li>
        </ul>
      </div>
    </div>
  );
}
