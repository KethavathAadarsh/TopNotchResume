"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  fetchEnhanceSession, triggerAnalysis, generateEnhanced, getDownloadUrl,
  type RseaSession, type SkillGap, type LearningItem, type ResumeImprovement,
  type InterviewTopic, type RseaVersion, type AgentStatus,
} from "@/lib/api";

// ── Utility helpers ──────────────────────────────────────────────────────────

const SEVERITY_COLOR: Record<string, string> = {
  critical: "border-red-500/40 bg-red-500/8 text-red-400",
  high:     "border-orange-500/40 bg-orange-500/8 text-orange-400",
  medium:   "border-yellow-500/40 bg-yellow-500/8 text-yellow-400",
  low:      "border-slate-600 bg-slate-800/40 text-slate-400",
};
const SEVERITY_BADGE: Record<string, string> = {
  critical: "bg-red-500/20 text-red-400 border-red-500/30",
  high:     "bg-orange-500/20 text-orange-400 border-orange-500/30",
  medium:   "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  low:      "bg-slate-700 text-slate-400 border-slate-600",
};
const PRIORITY_LABEL: Record<string, string> = {
  critical: "Critical", high: "High", medium: "Medium", low: "Low",
};
const AGENT_LABEL: Record<string, string> = {
  skill_gap:      "Skill Gap Analyst",
  resume_quality: "Resume Quality Agent",
  learning_path:  "Learning Path Advisor",
  career_intel:   "Career Intel Agent",
};
const AGENT_ICON: Record<string, string> = {
  skill_gap: "🔍", resume_quality: "📝", learning_path: "🗺️", career_intel: "🎯",
};
const DEPTH_COLOR: Record<string, string> = {
  surface: "text-green-400", moderate: "text-yellow-400", deep: "text-red-400",
};

function ReadinessRing({ score }: { score: number }) {
  const color = score >= 75 ? "text-green-400" : score >= 55 ? "text-yellow-400" : "text-red-400";
  const barColor = score >= 75 ? "bg-green-500" : score >= 55 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="text-center">
      <div className={`text-5xl font-bold ${color}`}>
        {score}<span className="text-xl text-slate-500">/100</span>
      </div>
      <div className="w-full h-1.5 bg-border rounded-full mt-3">
        <div className={`h-full rounded-full transition-all duration-1000 ${barColor}`} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

function ScorePill({ label, value }: { label: string; value: number }) {
  const color = value >= 75 ? "text-green-400" : value >= 50 ? "text-yellow-400" : "text-red-400";
  return (
    <div className="card p-3 text-center">
      <div className={`text-xl font-bold ${color}`}>{value}</div>
      <div className="text-[10px] text-slate-500 mt-0.5 uppercase tracking-wide">{label}</div>
    </div>
  );
}

// ── Loading screen while 4 agents run ────────────────────────────────────────

function AnalysisLoader({ progress }: { progress: Record<string, AgentStatus> }) {
  return (
    <div className="space-y-6 py-8">
      <div className="text-center">
        <div className="inline-flex items-center gap-2 mb-4">
          <div className="w-2 h-2 rounded-full bg-brand-500 animate-pulse" />
          <span className="text-sm font-medium text-brand-400">JARVIS is analyzing your career fit</span>
          <div className="w-2 h-2 rounded-full bg-brand-500 animate-pulse" style={{ animationDelay: "0.3s" }} />
        </div>
        <p className="text-xs text-slate-500">4 specialist agents running in parallel — usually 60–180 seconds</p>
      </div>
      <div className="space-y-3 max-w-md mx-auto">
        {Object.entries(AGENT_LABEL).map(([key, label]) => {
          const status = progress[key] || "pending";
          const isDone = status === "done";
          const isRunning = status === "running";
          return (
            <div key={key} className={`card p-3.5 flex items-center gap-3 transition-all duration-300 ${
              isRunning ? "border-brand-500/50 bg-brand-500/5" :
              isDone    ? "opacity-70" : "opacity-30"
            }`}>
              <span className="text-xl">{AGENT_ICON[key]}</span>
              <div className="flex-1">
                <p className="text-sm font-medium text-white">{label}</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  {isDone ? "Complete" : isRunning ? "Running..." : "Waiting"}
                </p>
              </div>
              <div className={`w-5 h-5 rounded-full flex items-center justify-center text-xs ${
                isDone    ? "bg-green-500/20 text-green-400 border border-green-500/30" :
                isRunning ? "bg-brand-500/20 text-brand-400 border border-brand-500/40 animate-pulse" :
                            "bg-border text-slate-600 border border-border"
              }`}>
                {isDone ? "✓" : isRunning ? "◌" : "·"}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Tab 1: Job Fit Analysis ───────────────────────────────────────────────────

function GapCard({ gap }: { gap: SkillGap }) {
  return (
    <div className={`card p-4 border ${SEVERITY_COLOR[gap.severity]} space-y-2`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full border ${SEVERITY_BADGE[gap.severity]}`}>
              {PRIORITY_LABEL[gap.severity]}
            </span>
            {gap.is_mandatory && (
              <span className="text-[10px] text-red-400 font-medium">Mandatory</span>
            )}
          </div>
          <p className="text-sm font-semibold text-white mt-1.5">{gap.skill}</p>
          <p className="text-[11px] text-slate-500 mt-0.5">{gap.category}</p>
        </div>
      </div>
      <p className="text-xs text-slate-400">{gap.jd_context}</p>
      {gap.candidate_adjacent && (
        <p className="text-xs text-brand-400/80">
          ✦ You have: {gap.candidate_adjacent}
        </p>
      )}
    </div>
  );
}

function FitTab({ report }: { report: NonNullable<RseaSession["career_report"]> }) {
  const sg = report.skill_gap;
  if (!sg) return <p className="text-sm text-slate-500">Skill gap data unavailable.</p>;

  const bySeverity = (s: string) => sg.skill_gaps.filter(g => g.severity === s);

  return (
    <div className="space-y-6">
      {/* Readiness score */}
      <div className="card p-6">
        <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-3">Overall Job Readiness</p>
        <ReadinessRing score={sg.overall_readiness_score} />
        <p className="text-sm font-semibold text-white text-center mt-3">{sg.readiness_label}</p>
        <p className="text-xs text-slate-400 text-center mt-2 leading-relaxed max-w-lg mx-auto">{sg.readiness_summary}</p>
      </div>

      {/* Critical blockers */}
      {sg.critical_blockers.length > 0 && (
        <div className="card p-4 border-red-500/30 bg-red-500/5">
          <p className="text-xs text-red-400 font-semibold uppercase tracking-wide mb-2">⚠ Critical Blockers — Fix Before Applying</p>
          <ul className="space-y-1">
            {sg.critical_blockers.map((b, i) => (
              <li key={i} className="text-xs text-red-300 flex items-start gap-2">
                <span className="text-red-500 mt-0.5">✗</span>{b}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Strengths */}
      {sg.strengths.length > 0 && (
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">Your Strengths for This Role</p>
          <div className="flex flex-wrap gap-2">
            {sg.strengths.map((s, i) => (
              <span key={i} className="text-xs bg-green-500/10 border border-green-500/20 text-green-400 rounded-full px-3 py-1">{s}</span>
            ))}
          </div>
        </div>
      )}

      {/* Competitive advantages */}
      {sg.competitive_advantages?.length > 0 && (
        <div className="card p-4 border-brand-500/20 bg-brand-500/5">
          <p className="text-xs text-brand-400 font-semibold uppercase tracking-wide mb-2">✦ Competitive Advantages</p>
          <ul className="space-y-1">
            {sg.competitive_advantages.map((a, i) => (
              <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                <span className="text-brand-400 mt-0.5">→</span>{a}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Skill gaps by severity */}
      {["critical","high","medium","low"].map(sev => {
        const gaps = bySeverity(sev);
        if (!gaps.length) return null;
        return (
          <div key={sev}>
            <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">
              {PRIORITY_LABEL[sev]} Priority Gaps ({gaps.length})
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {gaps.map((g, i) => <GapCard key={i} gap={g} />)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Tab 2: Learning Roadmap ───────────────────────────────────────────────────

function LearningCard({ item }: { item: LearningItem }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`card p-4 space-y-3 border ${SEVERITY_COLOR[item.priority]}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full border ${SEVERITY_BADGE[item.priority]}`}>
              {PRIORITY_LABEL[item.priority]}
            </span>
            <span className="text-xs text-slate-500">~{item.estimated_weeks}w</span>
          </div>
          <p className="text-sm font-semibold text-white">{item.skill}</p>
          <p className="text-xs text-slate-400 mt-0.5">{item.why_matters}</p>
        </div>
        <button onClick={() => setOpen(o => !o)} className="text-xs text-brand-400 hover:text-brand-300 shrink-0">
          {open ? "▲" : "▼"}
        </button>
      </div>

      {open && (
        <div className="space-y-3 pt-2 border-t border-border">
          {/* Resources */}
          <div>
            <p className="text-[10px] text-slate-500 uppercase tracking-wide font-medium mb-1.5">Resources</p>
            <ul className="space-y-1.5">
              {item.resources.map((r, i) => (
                <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                  <span className="text-brand-400 shrink-0 mt-0.5">
                    {r.type === "book" ? "📚" : r.type === "course" ? "🎓" : r.type === "platform" ? "💻" : "🔗"}
                  </span>
                  <span><strong className="text-white">{r.name}</strong> — {r.why}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Project idea */}
          <div className="bg-brand-500/5 border border-brand-500/20 rounded-lg p-3">
            <p className="text-[10px] text-brand-400 uppercase tracking-wide font-medium mb-1">
              {item.project_idea.github_ready ? "🚀 Portfolio Project" : "💡 Practice Project"}
            </p>
            <p className="text-xs font-semibold text-white">{item.project_idea.title}</p>
            <p className="text-xs text-slate-400 mt-1">{item.project_idea.description}</p>
            {item.project_idea.tech_stack.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {item.project_idea.tech_stack.map((t, i) => (
                  <span key={i} className="text-[10px] bg-slate-700 text-slate-300 rounded px-1.5 py-0.5">{t}</span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function RoadmapTab({ report }: { report: NonNullable<RseaSession["career_report"]> }) {
  const lp = report.learning_path;
  if (!lp) return <p className="text-sm text-slate-500">Learning path data unavailable.</p>;

  return (
    <div className="space-y-6">
      {/* Executive summary */}
      <div className="card p-5 border-brand-500/20 bg-brand-500/5">
        <div className="flex items-start gap-3">
          <span className="text-2xl">🗺️</span>
          <div>
            <p className="text-sm font-semibold text-white">Your Roadmap to Job-Ready</p>
            <p className="text-xs text-slate-400 mt-1">{lp.executive_summary}</p>
            <p className="text-xs text-brand-400 font-medium mt-2">Timeline: {lp.total_prep_timeline}</p>
          </div>
        </div>
      </div>

      {/* Quick wins */}
      {lp.quick_wins?.length > 0 && (
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">⚡ Quick Wins — Do This Week</p>
          <div className="space-y-2">
            {lp.quick_wins.map((w, i) => (
              <div key={i} className="card p-3 flex items-start gap-3">
                <span className="text-green-400 font-bold text-sm shrink-0">{i + 1}</span>
                <div>
                  <p className="text-xs text-white font-medium">{w.action}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[10px] text-slate-500">{w.time_required}</span>
                    <span className="text-[10px] text-brand-400">→ {w.impact}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Learning items */}
      {lp.learning_items.length > 0 && (
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">
            Skills to Learn ({lp.learning_items.length}) — click any card to expand
          </p>
          <div className="space-y-3">
            {lp.learning_items.map((item, i) => <LearningCard key={i} item={item} />)}
          </div>
        </div>
      )}

      {/* Certifications */}
      {lp.certifications?.length > 0 && (
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">Certifications to Pursue</p>
          <div className="space-y-3">
            {lp.certifications.map((cert, i) => (
              <div key={i} className="card p-4 space-y-1.5">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-white">{cert.name}</p>
                    <p className="text-xs text-slate-500">{cert.provider} · ~{cert.estimated_months} months</p>
                  </div>
                  <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full border shrink-0 ${SEVERITY_BADGE[cert.priority]}`}>
                    {cert.priority}
                  </span>
                </div>
                <p className="text-xs text-slate-400">{cert.relevance}</p>
                {cert.prep_resource && (
                  <p className="text-xs text-brand-400">Best prep: {cert.prep_resource}</p>
                )}
                {cert.exam_cost_usd && (
                  <p className="text-xs text-slate-600">Exam cost: ~${cert.exam_cost_usd}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* GitHub tips */}
      {lp.github_portfolio_tips && lp.github_portfolio_tips.length > 0 && (
        <div className="card p-4">
          <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">🐙 GitHub / Portfolio Tips</p>
          <ul className="space-y-1.5">
            {lp.github_portfolio_tips.map((tip, i) => (
              <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                <span className="text-brand-400 mt-0.5 shrink-0">→</span>{tip}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ── Tab 3: Resume Optimization ────────────────────────────────────────────────

function ImprovementCard({
  item, accepted, onToggle,
}: { item: ResumeImprovement; accepted: boolean; onToggle: (id: string) => void; }) {
  return (
    <div className={`card p-4 space-y-2 transition-all duration-200 ${accepted ? "ring-1 ring-brand-500/50" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full border ${SEVERITY_BADGE[item.priority]}`}>
              {PRIORITY_LABEL[item.priority]}
            </span>
            <span className="text-[10px] text-slate-600">{item.type.replace(/_/g, " ")}</span>
          </div>
          <p className="text-sm font-semibold text-white">{item.title}</p>
        </div>
        <button
          onClick={() => onToggle(item.id)}
          className={`shrink-0 text-xs px-3 py-1.5 rounded-md border transition-all font-medium ${
            accepted
              ? "bg-brand-500 border-brand-500 text-white"
              : "border-border text-slate-400 hover:border-brand-500/50 hover:text-brand-400"
          }`}
        >
          {accepted ? "✓ Apply" : "Apply"}
        </button>
      </div>
      <p className="text-xs text-slate-400 leading-relaxed">{item.description}</p>
      {item.example_fix && (
        <p className="text-xs text-slate-500 italic border-l-2 border-brand-500/30 pl-2">{item.example_fix}</p>
      )}
      <p className="text-xs text-brand-400/80 font-medium">{item.impact}</p>
      {item.keywords_to_add && item.keywords_to_add.length > 0 && (
        <div className="flex flex-wrap gap-1 pt-1">
          {item.keywords_to_add.slice(0, 8).map(kw => (
            <span key={kw} className="text-[10px] bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 rounded-full px-2 py-0.5">{kw}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function ResumeTab({
  report, accepted, onToggle, onGenerate, generating, genResult, genError, versions,
}: {
  report: NonNullable<RseaSession["career_report"]>;
  accepted: Set<string>;
  onToggle: (id: string) => void;
  onGenerate: () => void;
  generating: boolean;
  genResult: { version: number; download_id: string; ats_score: number } | null;
  genError: string;
  versions: RseaVersion[];
}) {
  const rq = report.resume_quality;
  if (!rq) return <p className="text-sm text-slate-500">Resume quality data unavailable.</p>;

  const improvements = rq.improvements || [];
  const high = improvements.filter(r => r.priority === "high");
  const mid  = improvements.filter(r => r.priority === "medium");
  const low  = improvements.filter(r => r.priority === "low");

  return (
    <div className="space-y-6">
      {/* Scores */}
      {rq.scores && (
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">Resume Quality Scores</p>
          <div className="grid grid-cols-3 md:grid-cols-5 gap-2">
            <ScorePill label="Bullets" value={rq.scores.bullet_quality} />
            <ScorePill label="ATS" value={rq.scores.ats_coverage} />
            <ScorePill label="Summary" value={rq.scores.summary_effectiveness} />
            <ScorePill label="Metrics" value={rq.scores.quantification_rate} />
            <ScorePill label="Leadership" value={rq.scores.leadership_language} />
          </div>
        </div>
      )}

      {/* Success banner */}
      {genResult && (
        <div className="card p-4 border-green-500/30 bg-green-500/5">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <p className="text-sm font-semibold text-green-400">
                ✅ v{genResult.version} generated — new ATS score: {Math.round(genResult.ats_score)}/100
              </p>
              <p className="text-xs text-slate-400 mt-0.5">
                Re-run analysis (click "Analyze Again") to get fresh recommendations for v{genResult.version}.
              </p>
            </div>
            <a href={getDownloadUrl(genResult.download_id)} download className="btn-primary text-sm px-4 py-2">
              ↓ Download v{genResult.version}
            </a>
          </div>
        </div>
      )}

      {/* Top missing keywords */}
      {rq.top_missing_keywords?.length > 0 && (
        <div className="card p-4">
          <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">Top Missing ATS Keywords</p>
          <div className="flex flex-wrap gap-1.5">
            {rq.top_missing_keywords.map(kw => (
              <span key={kw} className="text-xs bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 rounded-full px-2.5 py-0.5">{kw}</span>
            ))}
          </div>
        </div>
      )}

      {/* Improvements by priority */}
      {[["High Priority", high], ["Medium Priority", mid], ["Lower Priority", low]].map(([label, items]) => {
        const arr = items as ResumeImprovement[];
        if (!arr.length) return null;
        return (
          <div key={label as string}>
            <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">
              {label as string} ({arr.length})
            </p>
            <div className="space-y-3">
              {arr.map(item => (
                <ImprovementCard key={item.id} item={item} accepted={accepted.has(item.id)} onToggle={onToggle} />
              ))}
            </div>
          </div>
        );
      })}

      {genError && <p className="text-xs text-red-400 text-center">{genError}</p>}

      <div className="space-y-2 pt-2 border-t border-border">
        <p className="text-xs text-slate-500 text-center">
          {accepted.size} improvement{accepted.size !== 1 ? "s" : ""} selected
        </p>
        <button
          onClick={onGenerate}
          disabled={accepted.size === 0 || generating}
          className="btn-primary w-full py-3 text-sm disabled:opacity-40"
        >
          {generating
            ? "Generating refined version…"
            : accepted.size > 0
              ? `Generate v${versions.length + 1} — Apply ${accepted.size} Improvement${accepted.size > 1 ? "s" : ""} ✨`
              : "Select improvements above to generate"}
        </button>
        <p className="text-xs text-center text-slate-600">
          Creates a new versioned DOCX — previous versions stay downloadable
        </p>
      </div>
    </div>
  );
}

// ── Tab 4: Interview Intel ────────────────────────────────────────────────────

function InterviewCard({ topic }: { topic: InterviewTopic }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="card p-4 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-[10px] font-semibold uppercase tracking-wide ${DEPTH_COLOR[topic.depth]}`}>
              {topic.depth} dive
            </span>
          </div>
          <p className="text-sm font-semibold text-white">{topic.topic}</p>
          <p className="text-xs text-slate-400 mt-0.5">{topic.why}</p>
        </div>
        <button onClick={() => setOpen(o => !o)} className="text-xs text-brand-400 hover:text-brand-300 shrink-0">
          {open ? "▲" : "▼"}
        </button>
      </div>

      {open && (
        <div className="space-y-3 pt-2 border-t border-border">
          {topic.likely_questions.length > 0 && (
            <div>
              <p className="text-[10px] text-slate-500 uppercase tracking-wide font-medium mb-1.5">Likely Questions</p>
              <ul className="space-y-1.5">
                {topic.likely_questions.map((q, i) => (
                  <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                    <span className="text-yellow-400 mt-0.5 shrink-0">Q{i+1}.</span>{q}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {topic.candidate_angle && (
            <div className="bg-brand-500/5 border border-brand-500/20 rounded p-2.5">
              <p className="text-[10px] text-brand-400 uppercase tracking-wide font-medium mb-1">Your Angle</p>
              <p className="text-xs text-slate-300">{topic.candidate_angle}</p>
            </div>
          )}
          {topic.prep_resources.length > 0 && (
            <div>
              <p className="text-[10px] text-slate-500 uppercase tracking-wide font-medium mb-1">Prep Resources</p>
              <ul className="space-y-0.5">
                {topic.prep_resources.map((r, i) => (
                  <li key={i} className="text-xs text-brand-400">→ {r}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function IntelTab({ report }: { report: NonNullable<RseaSession["career_report"]> }) {
  const ci = report.career_intel;
  if (!ci) return <p className="text-sm text-slate-500">Career intel data unavailable.</p>;

  return (
    <div className="space-y-6">
      {/* Culture + company intel */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card p-4">
          <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">🏢 Culture Signals</p>
          <p className="text-xs text-slate-300 leading-relaxed">{ci.culture_signals}</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">📈 Company Stage Intel</p>
          <p className="text-xs text-slate-300 leading-relaxed">{ci.company_stage_intel}</p>
        </div>
      </div>

      {/* Role realities */}
      {ci.role_realities?.length > 0 && (
        <div className="card p-4">
          <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">⚡ Role Realities</p>
          <ul className="space-y-1.5">
            {ci.role_realities.map((r, i) => (
              <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                <span className="text-yellow-400 mt-0.5 shrink-0">→</span>{r}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Interview topics */}
      <div>
        <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">
          🎯 Interview Topics — click to expand
        </p>
        <div className="space-y-3">
          {ci.interview_prep.map((topic, i) => <InterviewCard key={i} topic={topic} />)}
        </div>
      </div>

      {/* Negotiation leverage */}
      {ci.negotiation_leverage?.length > 0 && (
        <div className="card p-4 border-green-500/20 bg-green-500/5">
          <p className="text-xs text-green-400 font-semibold uppercase tracking-wide mb-2">💰 Negotiation Leverage</p>
          <div className="space-y-2.5">
            {ci.negotiation_leverage.map((n, i) => (
              <div key={i}>
                <p className="text-xs font-medium text-white">{n.point}</p>
                <p className="text-xs text-slate-400 mt-0.5">{n.how_to_use}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Red flags */}
      {ci.red_flags?.length > 0 && (
        <div className="card p-4 border-red-500/20 bg-red-500/5">
          <p className="text-xs text-red-400 font-semibold uppercase tracking-wide mb-2">⚠ Red Flags to Probe</p>
          <ul className="space-y-1">
            {ci.red_flags.map((f, i) => (
              <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                <span className="text-red-400 mt-0.5 shrink-0">!</span>{f}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Application strategy */}
      {ci.application_strategy?.length > 0 && (
        <div className="card p-4">
          <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">🚀 Application Strategy</p>
          <ul className="space-y-1.5">
            {ci.application_strategy.map((s, i) => (
              <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                <span className="text-brand-400 mt-0.5 shrink-0">{i+1}.</span>{s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Questions to ask */}
      {ci.questions_to_ask?.length > 0 && (
        <div className="card p-4">
          <p className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2">❓ Smart Questions to Ask</p>
          <ul className="space-y-1.5">
            {ci.questions_to_ask.map((q, i) => (
              <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                <span className="text-brand-400 mt-0.5 shrink-0">→</span>{q}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

type Tab = "fit" | "roadmap" | "resume" | "intel";

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "fit",     label: "Job Fit",      icon: "🔍" },
  { id: "roadmap", label: "Learning Path", icon: "🗺️" },
  { id: "resume",  label: "Resume Fixes", icon: "📝" },
  { id: "intel",   label: "Interview Intel", icon: "🎯" },
];

export default function EnhanceClient() {
  // Query param (not a dynamic route) so the page works as a static export on GitHub Pages
  const sessionId = useSearchParams().get("id") ?? "";

  const [session, setSession] = useState<RseaSession | null>(null);
  const [loadError, setLoadError] = useState("");
  const [activeTab, setActiveTab] = useState<Tab>("fit");
  const [accepted, setAccepted] = useState<Set<string>>(new Set());
  const [generating, setGenerating] = useState(false);
  const [genResult, setGenResult] = useState<{ version: number; download_id: string; ats_score: number } | null>(null);
  const [genError, setGenError] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const refresh = useCallback(async () => {
    try {
      const s = await fetchEnhanceSession(sessionId);
      setSession(s);
      if (s.analysis_status === "ready" || s.analysis_status === "error") {
        stopPolling();
      }
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Failed to load session");
      stopPolling();
    }
  }, [sessionId]);

  // On mount: fetch, then trigger analysis if needed, then poll until ready
  useEffect(() => {
    (async () => {
      try {
        const s = await fetchEnhanceSession(sessionId);
        setSession(s);
        if (s.analysis_status === "pending") {
          await triggerAnalysis(sessionId);
          // Start polling
          pollRef.current = setInterval(refresh, 2500);
        } else if (s.analysis_status === "analyzing") {
          pollRef.current = setInterval(refresh, 2500);
        }
        // If "ready" or "error", nothing more to do
      } catch (err) {
        setLoadError(err instanceof Error ? err.message : "Failed to load session");
      }
    })();
    return () => stopPolling();
  }, [sessionId, refresh]);

  async function handleReanalyze() {
    setGenResult(null);
    setAccepted(new Set());
    await triggerAnalysis(sessionId);
    setSession(prev => prev ? { ...prev, analysis_status: "analyzing" } : prev);
    stopPolling();
    pollRef.current = setInterval(refresh, 2500);
  }

  async function handleGenerate() {
    if (accepted.size === 0 || !session) return;
    setGenerating(true);
    setGenError("");
    try {
      const result = await generateEnhanced(sessionId, Array.from(accepted));
      setGenResult({ version: result.version, download_id: result.download_id, ats_score: result.ats_score });
      setAccepted(new Set());
      // Refresh session for updated versions list
      await refresh();
    } catch (err) {
      setGenError(err instanceof Error ? err.message : "Enhancement failed");
    } finally {
      setGenerating(false);
    }
  }

  function toggleAccept(id: string) {
    setAccepted(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const isAnalyzing = session?.analysis_status === "analyzing";
  const isReady     = session?.analysis_status === "ready";
  const isError     = session?.analysis_status === "error";
  const readinessScore = session?.career_report?.skill_gap?.overall_readiness_score;
  const currentVersion = session?.versions[session.versions.length - 1];

  return (
    <div className="min-h-screen bg-surface">
      {/* Nav */}
      <nav className="border-b border-border px-6 py-4 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
          <span className="text-base font-bold text-white">TopNotch</span>
          <span className="text-base font-bold text-brand-500">Resume</span>
        </Link>
        <div className="flex items-center gap-3">
          {isReady && (
            <button
              onClick={handleReanalyze}
              className="text-xs text-brand-400 hover:text-brand-300 transition-colors border border-brand-500/30 rounded px-3 py-1.5"
            >
              ↺ Analyze Again
            </button>
          )}
          <span className="text-xs text-slate-600">JARVIS Career Intelligence · RSEA v2</span>
        </div>
      </nav>

      <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">

        {/* Header + version history */}
        <div className="space-y-4">
          <div>
            <h1 className="text-xl font-bold text-white">Career Intelligence Report</h1>
            <p className="text-sm text-slate-500 mt-1">
              4 specialist agents analyzing your fit, gaps, learning path, and interview strategy.
            </p>
          </div>

          {/* Version history strip */}
          {session && session.versions.length > 0 && (
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-xs text-slate-600 uppercase tracking-wide">Versions:</span>
              {session.versions.map(v => {
                const isCurrent = v.version === session.versions.length;
                const color = v.ats_score >= 80 ? "text-green-400" : v.ats_score >= 60 ? "text-yellow-400" : "text-red-400";
                return (
                  <div key={v.version} className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs ${isCurrent ? "border-brand-500/50 bg-brand-500/5" : "border-border opacity-60"}`}>
                    <span className="text-slate-400">v{v.version}</span>
                    <span className={`font-bold ${color}`}>{Math.round(v.ats_score)}</span>
                    <a href={getDownloadUrl(v.download_id)} download className="text-brand-400 hover:text-brand-300">↓</a>
                  </div>
                );
              })}
              {readinessScore !== undefined && (
                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-brand-500/30 bg-brand-500/5 text-xs">
                  <span className="text-slate-400">Readiness</span>
                  <span className={`font-bold ${readinessScore >= 75 ? "text-green-400" : readinessScore >= 55 ? "text-yellow-400" : "text-red-400"}`}>
                    {readinessScore}/100
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Error state */}
        {loadError && (
          <div className="card p-6 text-center">
            <p className="text-sm text-red-400">{loadError}</p>
          </div>
        )}

        {/* Analysis loading */}
        {(isAnalyzing || (session && session.analysis_status === "pending")) && (
          <AnalysisLoader progress={session?.agent_progress || {}} />
        )}

        {/* Analysis error */}
        {isError && (
          <div className="card p-6 text-center space-y-3">
            <p className="text-sm text-red-400">Analysis failed: {session?.analysis_error}</p>
            <button onClick={handleReanalyze} className="btn-secondary text-sm px-4 py-2">Retry Analysis</button>
          </div>
        )}

        {/* Dashboard */}
        {isReady && session?.career_report && (
          <div className="space-y-4">
            {/* Tabs */}
            <div className="flex gap-1 bg-surface border border-border rounded-lg p-1">
              {TABS.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex-1 flex items-center justify-center gap-1.5 text-xs py-2 px-2 rounded-md transition-all font-medium ${
                    activeTab === tab.id
                      ? "bg-brand-500 text-white"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  <span>{tab.icon}</span>
                  <span className="hidden sm:inline">{tab.label}</span>
                </button>
              ))}
            </div>

            {/* Tab content */}
            {activeTab === "fit"     && <FitTab report={session.career_report} />}
            {activeTab === "roadmap" && <RoadmapTab report={session.career_report} />}
            {activeTab === "resume"  && (
              <ResumeTab
                report={session.career_report}
                accepted={accepted}
                onToggle={toggleAccept}
                onGenerate={handleGenerate}
                generating={generating}
                genResult={genResult}
                genError={genError}
                versions={session.versions}
              />
            )}
            {activeTab === "intel"   && <IntelTab report={session.career_report} />}
          </div>
        )}

        {/* Navigation */}
        <div className="flex items-center justify-between text-xs text-slate-600 pt-2 border-t border-border">
          <Link href="/generate" className="hover:text-slate-400 transition-colors">← Generate new resume</Link>
          <Link href="/history" className="hover:text-slate-400 transition-colors">View history →</Link>
        </div>
      </div>
    </div>
  );
}
