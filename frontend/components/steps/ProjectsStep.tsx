"use client";
import { useState } from "react";
import type { CandidateProfile, ProjectEntry } from "@/types/resume";
import { SmartExtract } from "@/components/SmartExtract";

interface Props {
  profile: CandidateProfile;
  onChange: (updates: Partial<CandidateProfile>) => void;
}

const EMPTY_PROJ: ProjectEntry = {
  name: "",
  description: "",
  technologies: [],
  bullets: [""],
  url: "",
  github_url: "",
};

export function ProjectsStep({ profile, onChange }: Props) {
  const [expanded, setExpanded] = useState<number>(0);
  const [techInput, setTechInput] = useState<Record<number, string>>({});

  function handleExtract(data: Record<string, unknown>) {
    const extracted = (data.projects as ProjectEntry[]) || [];
    if (extracted.length === 0) return;
    const normalised = extracted.map(p => ({
      ...p,
      bullets: Array.isArray(p.bullets) && p.bullets.length ? p.bullets : [""],
      technologies: Array.isArray(p.technologies) ? p.technologies : [],
      url: p.url || "",
      github_url: p.github_url || "",
      description: p.description || "",
    }));
    const existing = profile.projects;
    const existingNames = new Set(existing.map(p => p.name.toLowerCase()));
    const newProjects = normalised.filter(p => !existingNames.has(p.name.toLowerCase()));
    onChange({ projects: [...existing, ...newProjects] });
    setExpanded(existing.length);
  }

  function update(index: number, updates: Partial<ProjectEntry>) {
    onChange({ projects: profile.projects.map((p, i) => (i === index ? { ...p, ...updates } : p)) });
  }

  function addTech(i: number) {
    const val = (techInput[i] || "").trim();
    if (!val) return;
    update(i, { technologies: [...profile.projects[i].technologies, val] });
    setTechInput(prev => ({ ...prev, [i]: "" }));
  }

  function removeTech(i: number, ti: number) {
    update(i, { technologies: profile.projects[i].technologies.filter((_, idx) => idx !== ti) });
  }

  function updateBullet(i: number, bi: number, val: string) {
    const bullets = profile.projects[i].bullets.map((b, idx) => idx === bi ? val : b);
    update(i, { bullets });
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-white mb-1">Projects</h2>
        <p className="text-sm text-slate-500">
          Paste your project descriptions and AI will extract them, or add manually.
        </p>
      </div>

      <SmartExtract
        section="projects"
        onExtracted={handleExtract}
      />

      {profile.projects.length === 0 && (
        <div className="card p-6 text-center border-dashed">
          <p className="text-slate-500 text-sm mb-3">No projects yet. Use AI extract above or add manually.</p>
          <button onClick={() => { onChange({ projects: [{ ...EMPTY_PROJ, bullets: [""] }] }); setExpanded(0); }} className="btn-primary text-sm">
            + Add Manually
          </button>
        </div>
      )}

      {profile.projects.map((proj, i) => (
        <div key={i} className="card overflow-hidden">
          <button
            className="w-full flex items-center justify-between p-4 text-left hover:bg-white/5"
            onClick={() => setExpanded(expanded === i ? -1 : i)}
          >
            <div>
              <p className="text-sm font-semibold text-white">{proj.name || "Untitled Project"}</p>
              {(proj.technologies?.length ?? 0) > 0 && (
                <p className="text-xs text-slate-500 mt-0.5">{proj.technologies.slice(0, 4).join(", ")}{proj.technologies.length > 4 ? "..." : ""}</p>
              )}
            </div>
            <div className="flex items-center gap-3">
              <button onClick={e => { e.stopPropagation(); onChange({ projects: profile.projects.filter((_, idx) => idx !== i) }); }} className="text-xs text-red-400">Remove</button>
              <span className="text-slate-500 text-xs">{expanded === i ? "▲" : "▼"}</span>
            </div>
          </button>

          {expanded === i && (
            <div className="px-4 pb-5 pt-4 border-t border-border space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label-base">Project Name</label>
                  <input className="input-base" value={proj.name} onChange={e => update(i, { name: e.target.value })} placeholder="AI Resume Platform" />
                </div>
                <div>
                  <label className="label-base">Live URL</label>
                  <input className="input-base" value={proj.url || ""} onChange={e => update(i, { url: e.target.value })} placeholder="https://..." />
                </div>
                <div className="md:col-span-2">
                  <label className="label-base">GitHub URL</label>
                  <input className="input-base" value={proj.github_url || ""} onChange={e => update(i, { github_url: e.target.value })} placeholder="https://github.com/..." />
                </div>
              </div>

              <div>
                <label className="label-base">Technologies Used</label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {(proj.technologies ?? []).map((t, ti) => (
                    <span key={ti} className="inline-flex items-center gap-1 bg-[#1e2433] border border-border rounded-full px-3 py-1 text-xs text-slate-300">
                      {t}
                      <button onClick={() => removeTech(i, ti)} className="text-slate-600 hover:text-red-400 ml-1">✕</button>
                    </span>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input className="input-base flex-1 text-sm" value={techInput[i] || ""} onChange={e => setTechInput(prev => ({ ...prev, [i]: e.target.value }))} onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addTech(i); } }} placeholder="Python, FastAPI, LangGraph..." />
                  <button onClick={() => addTech(i)} className="btn-secondary text-sm px-4">Add</button>
                </div>
              </div>

              <div>
                <label className="label-base">Key Points</label>
                <div className="space-y-2">
                  {proj.bullets.map((b, bi) => (
                    <div key={bi} className="flex gap-2 items-start">
                      <span className="text-slate-600 mt-2.5 text-sm">•</span>
                      <input className="input-base flex-1" value={b} onChange={e => updateBullet(i, bi, e.target.value)} placeholder="What did you build and what was the impact?" />
                      {proj.bullets.length > 1 && <button onClick={() => update(i, { bullets: proj.bullets.filter((_, idx) => idx !== bi) })} className="text-slate-600 hover:text-red-400 mt-2 text-xs">✕</button>}
                    </div>
                  ))}
                </div>
                <button onClick={() => update(i, { bullets: [...proj.bullets, ""] })} className="text-xs text-brand-500 hover:text-brand-400 mt-2">+ Add point</button>
              </div>
            </div>
          )}
        </div>
      ))}

      {profile.projects.length > 0 && (
        <button onClick={() => { onChange({ projects: [...profile.projects, { ...EMPTY_PROJ, bullets: [""] }] }); setExpanded(profile.projects.length); }} className="btn-secondary text-sm w-full">
          + Add Another Project Manually
        </button>
      )}
    </div>
  );
}
