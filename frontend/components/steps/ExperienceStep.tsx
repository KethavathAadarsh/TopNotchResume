"use client";
import { useState } from "react";
import type { CandidateProfile, ExperienceEntry } from "@/types/resume";
import { SmartExtract } from "@/components/SmartExtract";

interface Props {
  profile: CandidateProfile;
  onChange: (updates: Partial<CandidateProfile>) => void;
}

const EMPTY_EXP: ExperienceEntry = {
  company: "",
  title: "",
  start_date: "",
  end_date: "Present",
  location: "",
  bullets: [""],
};

export function ExperienceStep({ profile, onChange }: Props) {
  const [expanded, setExpanded] = useState<number>(0);

  function handleExtract(data: Record<string, unknown>) {
    const extracted = (data.experience as ExperienceEntry[]) || [];
    if (extracted.length === 0) return;
    // Normalise: ensure each entry has at least one bullet
    const normalised = extracted.map(e => ({
      ...e,
      bullets: e.bullets?.length ? e.bullets : [""],
      end_date: e.end_date || "Present",
    }));
    // Merge: append to existing entries (deduplicate by company+title)
    const existing = profile.experience;
    const existingKeys = new Set(existing.map(e => `${e.company}|${e.title}`));
    const newEntries = normalised.filter(e => !existingKeys.has(`${e.company}|${e.title}`));
    onChange({ experience: [...existing, ...newEntries] });
    setExpanded(existing.length); // expand the first newly added entry
  }

  function updateEntry(index: number, updates: Partial<ExperienceEntry>) {
    const updated = profile.experience.map((e, i) => (i === index ? { ...e, ...updates } : e));
    onChange({ experience: updated });
  }

  function addEntry() {
    onChange({ experience: [...profile.experience, { ...EMPTY_EXP, bullets: [""] }] });
    setExpanded(profile.experience.length);
  }

  function removeEntry(index: number) {
    onChange({ experience: profile.experience.filter((_, i) => i !== index) });
    setExpanded(Math.max(0, expanded - 1));
  }

  function updateBullet(expIndex: number, bulletIndex: number, value: string) {
    const exp = profile.experience[expIndex];
    const bullets = exp.bullets.map((b, i) => (i === bulletIndex ? value : b));
    updateEntry(expIndex, { bullets });
  }

  function addBullet(expIndex: number) {
    const exp = profile.experience[expIndex];
    updateEntry(expIndex, { bullets: [...exp.bullets, ""] });
  }

  function removeBullet(expIndex: number, bulletIndex: number) {
    const exp = profile.experience[expIndex];
    updateEntry(expIndex, { bullets: exp.bullets.filter((_, i) => i !== bulletIndex) });
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-white mb-1">Work Experience</h2>
        <p className="text-sm text-slate-500">
          Paste your work history and AI will extract it, or add roles manually.
        </p>
      </div>

      <SmartExtract
        section="experience"
        onExtracted={handleExtract}
      />

      {profile.experience.length === 0 && (
        <div className="card p-6 text-center border-dashed">
          <p className="text-slate-500 text-sm mb-3">No experience entries yet. Use AI extract above or add manually.</p>
          <button onClick={addEntry} className="btn-primary text-sm">
            + Add Manually
          </button>
        </div>
      )}

      {profile.experience.map((exp, i) => (
        <div key={i} className="card overflow-hidden">
          <button
            className="w-full flex items-center justify-between p-4 text-left hover:bg-white/5 transition-colors"
            onClick={() => setExpanded(expanded === i ? -1 : i)}
          >
            <div>
              <p className="text-sm font-semibold text-white">
                {exp.title || "Untitled Role"}{" "}
                {exp.company && <span className="text-slate-400">@ {exp.company}</span>}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                {exp.start_date} {exp.start_date && "–"} {exp.end_date}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={(e) => { e.stopPropagation(); removeEntry(i); }}
                className="text-xs text-red-400 hover:text-red-300 transition-colors"
              >
                Remove
              </button>
              <span className="text-slate-500 text-xs">{expanded === i ? "▲" : "▼"}</span>
            </div>
          </button>

          {expanded === i && (
            <div className="px-4 pb-5 space-y-4 border-t border-border pt-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label-base">Job Title <span className="text-red-400">*</span></label>
                  <input className="input-base" value={exp.title} onChange={e => updateEntry(i, { title: e.target.value })} placeholder="Senior Software Engineer" />
                </div>
                <div>
                  <label className="label-base">Company <span className="text-red-400">*</span></label>
                  <input className="input-base" value={exp.company} onChange={e => updateEntry(i, { company: e.target.value })} placeholder="Stripe" />
                </div>
                <div>
                  <label className="label-base">Start Date</label>
                  <input className="input-base" value={exp.start_date} onChange={e => updateEntry(i, { start_date: e.target.value })} placeholder="Jan 2021" />
                </div>
                <div>
                  <label className="label-base">End Date</label>
                  <input className="input-base" value={exp.end_date} onChange={e => updateEntry(i, { end_date: e.target.value })} placeholder="Present" />
                </div>
                <div className="md:col-span-2">
                  <label className="label-base">Location</label>
                  <input className="input-base" value={exp.location || ""} onChange={e => updateEntry(i, { location: e.target.value })} placeholder="San Francisco, CA" />
                </div>
              </div>

              <div>
                <label className="label-base">Responsibilities / Achievements</label>
                <p className="text-xs text-slate-600 mb-2">Raw notes are fine — AI will optimize these into polished bullets.</p>
                <div className="space-y-2">
                  {exp.bullets.map((bullet, bi) => (
                    <div key={bi} className="flex gap-2 items-start">
                      <span className="text-slate-600 mt-2.5 text-sm">•</span>
                      <input
                        className="input-base flex-1"
                        value={bullet}
                        onChange={e => updateBullet(i, bi, e.target.value)}
                        placeholder="Built an API that handled 1M requests/day"
                      />
                      {exp.bullets.length > 1 && (
                        <button onClick={() => removeBullet(i, bi)} className="text-slate-600 hover:text-red-400 mt-2 transition-colors text-xs">✕</button>
                      )}
                    </div>
                  ))}
                </div>
                <button onClick={() => addBullet(i)} className="text-xs text-brand-500 hover:text-brand-400 mt-2 transition-colors">
                  + Add bullet
                </button>
              </div>
            </div>
          )}
        </div>
      ))}

      {profile.experience.length > 0 && (
        <button onClick={addEntry} className="btn-secondary text-sm w-full">
          + Add Another Role Manually
        </button>
      )}
    </div>
  );
}
