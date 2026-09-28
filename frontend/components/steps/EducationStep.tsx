"use client";
import { useState } from "react";
import type { CandidateProfile, EducationEntry, CertificationEntry } from "@/types/resume";
import { SmartExtract } from "@/components/SmartExtract";

interface Props {
  profile: CandidateProfile;
  onChange: (updates: Partial<CandidateProfile>) => void;
}

const EMPTY_EDU: EducationEntry = { institution: "", degree: "", field: "", graduation_date: "", gpa: "", honors: "" };
const EMPTY_CERT: CertificationEntry = { name: "", issuer: "", date: "" };

export function EducationStep({ profile, onChange }: Props) {
  const [certInput, setCertInput] = useState<CertificationEntry>({ ...EMPTY_CERT });

  function handleEduExtract(data: Record<string, unknown>) {
    const edu = (data.education as EducationEntry[]) || [];
    const certs = (data.certifications as CertificationEntry[]) || [];

    const updates: Partial<CandidateProfile> = {};
    if (edu.length > 0) {
      const existingKeys = new Set(profile.education.map(e => `${e.institution}|${e.degree}`));
      const newEdu = edu.filter(e => !existingKeys.has(`${e.institution}|${e.degree}`));
      updates.education = [...profile.education, ...newEdu];
    }
    if (certs.length > 0) {
      const existingNames = new Set(profile.certifications.map(c => c.name.toLowerCase()));
      const newCerts = certs.filter(c => !existingNames.has(c.name.toLowerCase()));
      updates.certifications = [...profile.certifications, ...newCerts];
    }
    if (Object.keys(updates).length > 0) onChange(updates);
  }

  function handleCertExtract(data: Record<string, unknown>) {
    const certs = (data.certifications as CertificationEntry[]) || [];
    if (certs.length === 0) return;
    const existingNames = new Set(profile.certifications.map(c => c.name.toLowerCase()));
    const newCerts = certs.filter(c => !existingNames.has(c.name.toLowerCase()));
    if (newCerts.length > 0) onChange({ certifications: [...profile.certifications, ...newCerts] });
  }

  function updateEdu(i: number, updates: Partial<EducationEntry>) {
    onChange({ education: profile.education.map((e, idx) => idx === i ? { ...e, ...updates } : e) });
  }

  function addCert() {
    if (!certInput.name) return;
    onChange({ certifications: [...profile.certifications, { ...certInput }] });
    setCertInput({ ...EMPTY_CERT });
  }

  return (
    <div className="space-y-6">
      {/* Education */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-1">Education & Certifications</h2>
        <p className="text-sm text-slate-500 mb-4">Paste your education/certs and AI will extract them, or add manually.</p>

        <SmartExtract
          section="education"
          label="Extract Education & Certifications"
          onExtracted={handleEduExtract}
        />

        {profile.education.map((edu, i) => (
          <div key={i} className="card p-4 mb-3 space-y-3">
            <div className="flex justify-between items-center">
              <p className="text-sm font-medium text-white">
                {edu.degree || "Degree"}{" "}
                {edu.institution && <span className="text-slate-400">· {edu.institution}</span>}
              </p>
              <button onClick={() => onChange({ education: profile.education.filter((_, idx) => idx !== i) })} className="text-xs text-red-400 hover:text-red-300">Remove</button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="label-base">Degree</label>
                <input className="input-base" value={edu.degree} onChange={e => updateEdu(i, { degree: e.target.value })} placeholder="Bachelor of Science" />
              </div>
              <div>
                <label className="label-base">Field of Study</label>
                <input className="input-base" value={edu.field} onChange={e => updateEdu(i, { field: e.target.value })} placeholder="Computer Science" />
              </div>
              <div>
                <label className="label-base">Institution</label>
                <input className="input-base" value={edu.institution} onChange={e => updateEdu(i, { institution: e.target.value })} placeholder="MIT" />
              </div>
              <div>
                <label className="label-base">Graduation Date</label>
                <input className="input-base" value={edu.graduation_date} onChange={e => updateEdu(i, { graduation_date: e.target.value })} placeholder="May 2020" />
              </div>
              <div>
                <label className="label-base">GPA (optional)</label>
                <input className="input-base" value={edu.gpa || ""} onChange={e => updateEdu(i, { gpa: e.target.value })} placeholder="3.9/4.0" />
              </div>
              <div>
                <label className="label-base">Honors (optional)</label>
                <input className="input-base" value={edu.honors || ""} onChange={e => updateEdu(i, { honors: e.target.value })} placeholder="Cum Laude, Dean's List" />
              </div>
            </div>
          </div>
        ))}

        <button onClick={() => onChange({ education: [...profile.education, { ...EMPTY_EDU }] })} className="btn-secondary text-sm w-full">
          + Add Education Manually
        </button>
      </div>

      {/* Certifications */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-base font-semibold text-white">Certifications</h3>
        </div>

        <SmartExtract
          section="certifications"
          label="Extract Certifications only"
          onExtracted={handleCertExtract}
        />

        {profile.certifications.map((cert, i) => (
          <div key={i} className="flex items-center gap-3 mb-2">
            <div className="card flex-1 px-4 py-2.5 flex items-center justify-between">
              <span className="text-sm text-slate-300">
                {cert.name}
                {cert.issuer && <span className="text-slate-500"> · {cert.issuer}</span>}
                {cert.date && <span className="text-slate-600"> · {cert.date}</span>}
              </span>
              <button onClick={() => onChange({ certifications: profile.certifications.filter((_, idx) => idx !== i) })} className="text-xs text-red-400 hover:text-red-300 ml-3">✕</button>
            </div>
          </div>
        ))}

        <div className="card p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="label-base">Certification Name</label>
              <input className="input-base" value={certInput.name} onChange={e => setCertInput(p => ({ ...p, name: e.target.value }))} placeholder="AWS Solutions Architect" />
            </div>
            <div>
              <label className="label-base">Issuing Organization</label>
              <input className="input-base" value={certInput.issuer} onChange={e => setCertInput(p => ({ ...p, issuer: e.target.value }))} placeholder="Amazon" />
            </div>
            <div>
              <label className="label-base">Date</label>
              <input className="input-base" value={certInput.date || ""} onChange={e => setCertInput(p => ({ ...p, date: e.target.value }))} placeholder="2024" />
            </div>
          </div>
          <button onClick={addCert} disabled={!certInput.name} className="btn-secondary text-sm px-4">
            + Add Manually
          </button>
        </div>
      </div>
    </div>
  );
}
