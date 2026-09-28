"use client";

interface Props {
  jobDescription: string;
  targetRole: string;
  onChangeJD: (val: string) => void;
  onChangeRole: (val: string) => void;
}

export function JobDescriptionStep({ jobDescription, targetRole, onChangeJD, onChangeRole }: Props) {
  const charCount = jobDescription.length;
  const isGood = charCount > 200;

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-white mb-1">Target Job Description</h2>
        <p className="text-sm text-slate-500">
          Paste the full job description. The more context JARVIS has, the better the tailoring.
        </p>
      </div>

      <div>
        <label className="label-base">Target Role Title (optional)</label>
        <input
          className="input-base"
          value={targetRole}
          onChange={e => onChangeRole(e.target.value)}
          placeholder="Senior Software Engineer"
        />
        <p className="text-xs text-slate-600 mt-1">Helps JARVIS align the summary and tone even if not in the JD.</p>
      </div>

      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label className="label-base">Job Description <span className="text-red-400">*</span></label>
          <span className={`text-xs ${isGood ? "text-green-500" : "text-slate-500"}`}>
            {charCount} chars {isGood ? "✓" : "(aim for 200+)"}
          </span>
        </div>
        <textarea
          className="input-base min-h-[300px] resize-y font-mono text-xs leading-relaxed"
          value={jobDescription}
          onChange={e => onChangeJD(e.target.value)}
          placeholder={`Paste the full job description here...

Example:
We're looking for a Senior Software Engineer to join our platform team at Stripe. You'll architect and build systems that handle billions of financial transactions...

Requirements:
- 5+ years of backend engineering experience
- Proficiency in Go, Python, or Java
- Experience with distributed systems and microservices
- Strong understanding of API design...`}
        />
      </div>

      {charCount > 0 && !isGood && (
        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3">
          <p className="text-xs text-yellow-400">
            Tip: A longer JD gives JARVIS more signal for keyword matching and tone calibration. Try pasting the full posting.
          </p>
        </div>
      )}
    </div>
  );
}
