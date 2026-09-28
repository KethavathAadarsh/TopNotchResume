"use client";
import type { CandidateProfile } from "@/types/resume";
import { SmartExtract } from "@/components/SmartExtract";

interface Props {
  profile: CandidateProfile;
  onChange: (updates: Partial<CandidateProfile>) => void;
}

export function PersonalInfoStep({ profile, onChange }: Props) {
  function handleFullExtract(data: Record<string, unknown>) {
    // "all" extraction can populate the whole profile at once
    const updates: Partial<CandidateProfile> = {};
    if (data.name) updates.name = data.name as string;
    if (data.email) updates.email = data.email as string;
    if (data.phone) updates.phone = data.phone as string;
    if (data.location) updates.location = data.location as string;
    if (data.linkedin) updates.linkedin = data.linkedin as string;
    if (data.github) updates.github = data.github as string;
    if (data.website) updates.website = data.website as string;
    if (data.summary) updates.summary = data.summary as string;
    if (Array.isArray(data.experience) && data.experience.length > 0)
      updates.experience = data.experience as CandidateProfile["experience"];
    if (Array.isArray(data.projects) && data.projects.length > 0)
      updates.projects = data.projects as CandidateProfile["projects"];
    if (Array.isArray(data.skill_categories) && data.skill_categories.length > 0)
      updates.skill_categories = data.skill_categories as CandidateProfile["skill_categories"];
    if (Array.isArray(data.education) && data.education.length > 0)
      updates.education = data.education as CandidateProfile["education"];
    if (Array.isArray(data.certifications) && data.certifications.length > 0)
      updates.certifications = data.certifications as CandidateProfile["certifications"];
    onChange(updates);
  }

  function handlePersonalExtract(data: Record<string, unknown>) {
    const updates: Partial<CandidateProfile> = {};
    if (data.name) updates.name = data.name as string;
    if (data.email) updates.email = data.email as string;
    if (data.phone) updates.phone = data.phone as string;
    if (data.location) updates.location = data.location as string;
    if (data.linkedin) updates.linkedin = data.linkedin as string;
    if (data.github) updates.github = data.github as string;
    if (data.website) updates.website = data.website as string;
    if (data.summary) updates.summary = data.summary as string;
    onChange(updates);
  }

  const field = (key: keyof CandidateProfile, label: string, placeholder: string, required = false) => (
    <div>
      <label className="label-base">
        {label} {required && <span className="text-red-400">*</span>}
      </label>
      <input
        className="input-base"
        value={(profile[key] as string) || ""}
        onChange={(e) => onChange({ [key]: e.target.value })}
        placeholder={placeholder}
      />
    </div>
  );

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-white mb-1">Personal Information</h2>
        <p className="text-sm text-slate-500">Fill manually or let AI extract from pasted text.</p>
      </div>

      {/* Full resume import — fills everything across all steps */}
      <SmartExtract
        section="all"
        label="Import Full Resume (fills all sections)"
        onExtracted={handleFullExtract}
      />

      {/* Personal-only extractor */}
      <SmartExtract
        section="personal"
        label="Extract Contact Info only"
        onExtracted={handlePersonalExtract}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {field("name", "Full Name", "Jane Smith", true)}
        {field("email", "Email", "jane@example.com", true)}
        {field("phone", "Phone", "(555) 123-4567")}
        {field("location", "Location", "San Francisco, CA")}
        {field("linkedin", "LinkedIn URL", "linkedin.com/in/jane")}
        {field("github", "GitHub URL", "github.com/jane")}
        {field("website", "Personal Website", "janesmith.dev")}
      </div>

      <div>
        <label className="label-base">Professional Summary (optional — AI will generate one)</label>
        <textarea
          className="input-base min-h-[90px] resize-none"
          value={profile.summary || ""}
          onChange={(e) => onChange({ summary: e.target.value })}
          placeholder="Leave blank for AI to write a tailored summary based on your profile and target role."
        />
      </div>
    </div>
  );
}
