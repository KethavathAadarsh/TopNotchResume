"use client";
import { useState } from "react";
import type { CandidateProfile, SkillCategory } from "@/types/resume";
import { SmartExtract } from "@/components/SmartExtract";

interface Props {
  profile: CandidateProfile;
  onChange: (updates: Partial<CandidateProfile>) => void;
}

const SUGGESTED_CATEGORIES = [
  "Languages", "Frameworks", "Databases", "Cloud & Infrastructure",
  "AI / ML", "Tools & DevOps", "Architecture",
];

const EMPTY_CAT: SkillCategory = { category: "", items: [] };

export function SkillsStep({ profile, onChange }: Props) {
  const [newSkillInputs, setNewSkillInputs] = useState<Record<number, string>>({});

  function handleExtract(data: Record<string, unknown>) {
    const extracted = (data.skill_categories as SkillCategory[]) || [];
    const flatSkills = (data.flat_skills as string[]) || [];
    if (extracted.length === 0 && flatSkills.length === 0) return;

    // Merge categories — if same category name exists, merge items
    const merged = [...profile.skill_categories];
    for (const cat of extracted) {
      const existing = merged.find(c => c.category.toLowerCase() === cat.category.toLowerCase());
      if (existing) {
        const newItems = cat.items.filter(i => !existing.items.includes(i));
        existing.items = [...existing.items, ...newItems];
      } else {
        merged.push(cat);
      }
    }
    // Flat skills that don't fit categories — add to "Other" or as flat_skills
    const allFlat = [...new Set([...profile.flat_skills, ...flatSkills])];
    onChange({ skill_categories: merged, flat_skills: allFlat });
  }

  function updateCategory(index: number, updates: Partial<SkillCategory>) {
    const updated = profile.skill_categories.map((c, i) => (i === index ? { ...c, ...updates } : c));
    onChange({ skill_categories: updated });
  }

  function addCategory() {
    onChange({ skill_categories: [...profile.skill_categories, { ...EMPTY_CAT }] });
  }

  function removeCategory(index: number) {
    onChange({ skill_categories: profile.skill_categories.filter((_, i) => i !== index) });
  }

  function addSkillToCategory(index: number) {
    const val = (newSkillInputs[index] || "").trim();
    if (!val) return;
    const cat = profile.skill_categories[index];
    updateCategory(index, { items: [...cat.items, val] });
    setNewSkillInputs(prev => ({ ...prev, [index]: "" }));
  }

  function removeSkill(catIndex: number, skillIndex: number) {
    const cat = profile.skill_categories[catIndex];
    updateCategory(catIndex, { items: cat.items.filter((_, i) => i !== skillIndex) });
  }

  function useTemplate(name: string) {
    if (!profile.skill_categories.find(c => c.category === name)) {
      onChange({ skill_categories: [...profile.skill_categories, { category: name, items: [] }] });
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-white mb-1">Skills</h2>
        <p className="text-sm text-slate-500">Paste your skills list and AI will categorize them, or add manually.</p>
      </div>

      <SmartExtract
        section="skills"
        onExtracted={handleExtract}
      />

      {/* Quick-add templates */}
      <div>
        <p className="label-base mb-2">Quick-add category</p>
        <div className="flex flex-wrap gap-2">
          {SUGGESTED_CATEGORIES.map(c => (
            <button
              key={c}
              onClick={() => useTemplate(c)}
              className="text-xs bg-brand-500/10 border border-brand-500/20 text-brand-400 rounded-full px-3 py-1 hover:bg-brand-500/20 transition-colors"
            >
              + {c}
            </button>
          ))}
        </div>
      </div>

      {profile.skill_categories.length === 0 && (
        <div className="card p-5 text-center border-dashed">
          <p className="text-slate-500 text-sm">Use AI extract above or add a category manually.</p>
        </div>
      )}

      {profile.skill_categories.map((cat, i) => (
        <div key={i} className="card p-4 space-y-3">
          <div className="flex items-center gap-3">
            <input
              className="input-base flex-1 font-medium"
              value={cat.category}
              onChange={e => updateCategory(i, { category: e.target.value })}
              placeholder="Category name (e.g. Languages)"
            />
            <button onClick={() => removeCategory(i)} className="text-xs text-red-400 hover:text-red-300 shrink-0">
              Remove
            </button>
          </div>

          <div className="flex flex-wrap gap-2">
            {cat.items.map((skill, si) => (
              <span
                key={si}
                className="inline-flex items-center gap-1 bg-[#1e2433] border border-border rounded-full px-3 py-1 text-xs text-slate-300"
              >
                {skill}
                <button onClick={() => removeSkill(i, si)} className="text-slate-600 hover:text-red-400 ml-1">✕</button>
              </span>
            ))}
          </div>

          <div className="flex gap-2">
            <input
              className="input-base flex-1 text-sm"
              value={newSkillInputs[i] || ""}
              onChange={e => setNewSkillInputs(prev => ({ ...prev, [i]: e.target.value }))}
              onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addSkillToCategory(i); } }}
              placeholder="Type skill and press Enter"
            />
            <button onClick={() => addSkillToCategory(i)} className="btn-secondary text-sm px-4">Add</button>
          </div>
        </div>
      ))}

      <button onClick={addCategory} className="btn-secondary text-sm w-full">
        + Add Skill Category Manually
      </button>
    </div>
  );
}
