"use client";
import { useCallback, useEffect, useState } from "react";
import type { CandidateProfile, GenerateRequest, GenerateResponse, ResumeFormat } from "@/types/resume";
import { EMPTY_PROFILE } from "@/types/resume";
import { startGenerationAsync, fetchRestoreProfile } from "@/lib/api";
import { ProgressBar } from "@/components/ProgressBar";
import { PersonalInfoStep } from "@/components/steps/PersonalInfoStep";
import { ExperienceStep } from "@/components/steps/ExperienceStep";
import { SkillsStep } from "@/components/steps/SkillsStep";
import { ProjectsStep } from "@/components/steps/ProjectsStep";
import { EducationStep } from "@/components/steps/EducationStep";
import { JobDescriptionStep } from "@/components/steps/JobDescriptionStep";
import { OutputOptionsStep } from "@/components/steps/OutputOptionsStep";
import { GeneratingStep } from "@/components/GeneratingStep";
import { DownloadStep } from "@/components/DownloadStep";
import { ModelSelectorModal } from "@/components/ModelSelectorModal";

const DEFAULT_MODEL = "claude-opus-5";

const STEPS = [
  "Personal Info",
  "Experience",
  "Skills",
  "Projects",
  "Education",
  "Job Description",
  "Output Options",
];

type WizardState = "form" | "generating" | "done";

interface WizardProps {
  restoreId?: string;
}

export function ResumeWizard({ restoreId }: WizardProps = {}) {
  const [step, setStep] = useState(0);
  const [profile, setProfile] = useState<CandidateProfile>({ ...EMPTY_PROFILE });
  const [jobDescription, setJobDescription] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [format, setFormat] = useState<ResumeFormat>("ats");
  const [maxPages, setMaxPages] = useState<1 | 2>(1);
  const [wizardState, setWizardState] = useState<WizardState>("form");
  const [isRestoring, setIsRestoring] = useState(!!restoreId);
  const [restoreError, setRestoreError] = useState("");

  // Pre-fill all sections when restoreId is present
  useEffect(() => {
    if (!restoreId) return;
    setIsRestoring(true);
    fetchRestoreProfile(restoreId)
      .then((data) => {
        setProfile({ ...EMPTY_PROFILE, ...data.profile });
        if (data.job_description) setJobDescription(data.job_description);
        if (data.target_role) setTargetRole(data.target_role);
        if (data.format) setFormat(data.format as ResumeFormat);
        if (data.max_pages) setMaxPages(data.max_pages as 1 | 2);
        // Land on Output Options so user can review and re-generate immediately
        setStep(6);
      })
      .catch((err: Error) => setRestoreError(err.message || "Failed to load saved session"))
      .finally(() => setIsRestoring(false));
  }, [restoreId]);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [error, setError] = useState("");
  const [jobId, setJobId] = useState<string>("");
  const [selectedModel, setSelectedModel] = useState(DEFAULT_MODEL);
  const [showModelModal, setShowModelModal] = useState(false);

  function updateProfile(updates: Partial<CandidateProfile>) {
    setProfile(prev => ({ ...prev, ...updates }));
  }

  function canProceed(): boolean {
    if (step === 0) return !!profile.name && !!profile.email;
    if (step === 5) return jobDescription.length > 50;
    return true;
  }

  function handleGenerate() {
    setShowModelModal(true);
  }

  async function handleModelConfirm() {
    setShowModelModal(false);
    setWizardState("generating");
    setError("");

    const request: GenerateRequest = {
      profile,
      job_description: jobDescription,
      format,
      max_pages: maxPages,
      target_role: targetRole || undefined,
      model: selectedModel,
    };

    try {
      const { job_id } = await startGenerationAsync(request);
      setJobId(job_id);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
    }
  }

  const handleSSEComplete = useCallback((raw: Record<string, unknown>) => {
    const res: GenerateResponse = {
      download_id: raw.download_id as string,
      session_id: raw.session_id as string | undefined,
      ats_score: raw.ats_score as number,
      keywords_matched: raw.keywords_matched as string[],
      keywords_missing: raw.keywords_missing as string[],
      sections_included: raw.sections_included as string[],
      generation_time_ms: raw.generation_time_ms as number,
    };
    setResult(res);
    setWizardState("done");
  }, []);

  const handleSSEError = useCallback((msg: string) => {
    setError(msg);
  }, []);

  function handleRestart() {
    setProfile({ ...EMPTY_PROFILE });
    setJobDescription("");
    setTargetRole("");
    setFormat("ats");
    setMaxPages(1);
    setStep(0);
    setResult(null);
    setError("");
    setJobId("");
    setWizardState("form");
  }

  if (isRestoring) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8 flex flex-col items-center gap-4 text-center">
        <div className="w-10 h-10 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-white font-medium">Loading saved session…</p>
        <p className="text-xs text-slate-500">Restoring all 7 sections from your previous generation</p>
      </div>
    );
  }

  if (restoreError) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8 text-center space-y-4">
        <p className="text-red-400 font-medium">Could not restore session</p>
        <p className="text-xs text-slate-500">{restoreError}</p>
        <button onClick={() => { setRestoreError(""); setStep(0); }} className="btn-primary text-sm">
          Start Fresh
        </button>
      </div>
    );
  }

  if (wizardState === "generating") {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8">
        <GeneratingStep
          jobId={jobId || undefined}
          error={error || undefined}
          onComplete={handleSSEComplete}
          onError={handleSSEError}
        />
        {error && (
          <button
            onClick={() => { setWizardState("form"); setStep(6); setJobId(""); }}
            className="btn-secondary text-sm w-full mt-6"
          >
            ← Back to Options
          </button>
        )}
      </div>
    );
  }

  if (wizardState === "done" && result) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8">
        <DownloadStep result={result} onRestart={handleRestart} selectedModel={selectedModel} />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="mb-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-white">Build Your Resume</h1>
            <p className="text-sm text-slate-500 mt-0.5">Powered by JARVIS · Multi-Agent AI v2</p>
          </div>
        </div>
        <ProgressBar currentStep={step} totalSteps={STEPS.length} stepLabels={STEPS} />
      </div>

      <div className="card p-6 mb-6">
        {step === 0 && <PersonalInfoStep profile={profile} onChange={updateProfile} />}
        {step === 1 && <ExperienceStep profile={profile} onChange={updateProfile} />}
        {step === 2 && <SkillsStep profile={profile} onChange={updateProfile} />}
        {step === 3 && <ProjectsStep profile={profile} onChange={updateProfile} />}
        {step === 4 && <EducationStep profile={profile} onChange={updateProfile} />}
        {step === 5 && (
          <JobDescriptionStep
            jobDescription={jobDescription}
            targetRole={targetRole}
            onChangeJD={setJobDescription}
            onChangeRole={setTargetRole}
          />
        )}
        {step === 6 && (
          <OutputOptionsStep
            format={format}
            maxPages={maxPages}
            onChangeFormat={setFormat}
            onChangePages={setMaxPages}
          />
        )}
      </div>

      <div className="flex items-center justify-between gap-4">
        <button
          onClick={() => setStep(s => Math.max(0, s - 1))}
          disabled={step === 0}
          className="btn-secondary disabled:opacity-30"
        >
          ← Back
        </button>

        <div className="flex items-center gap-2">
          {STEPS.map((_, i) => (
            <button
              key={i}
              onClick={() => setStep(i)}
              className={`w-2 h-2 rounded-full transition-colors duration-150 ${
                i === step ? "bg-brand-500" : i < step ? "bg-brand-500/40" : "bg-border"
              }`}
            />
          ))}
        </div>

        {step < STEPS.length - 1 ? (
          <button
            onClick={() => setStep(s => s + 1)}
            disabled={!canProceed()}
            className="btn-primary disabled:opacity-50"
          >
            Next →
          </button>
        ) : (
          <button
            onClick={handleGenerate}
            disabled={!canProceed()}
            className="btn-primary disabled:opacity-50 px-6"
          >
            Generate Resume ✨
          </button>
        )}
      </div>

      {(step === 2 || step === 3 || step === 4) && (
        <p className="text-center text-xs text-slate-600 mt-4">
          This section is optional. Skip if not applicable.
        </p>
      )}

      <ModelSelectorModal
        isOpen={showModelModal}
        selectedModel={selectedModel}
        onSelect={setSelectedModel}
        onConfirm={handleModelConfirm}
        onCancel={() => setShowModelModal(false)}
        confirmLabel="Start Generation →"
      />
    </div>
  );
}
