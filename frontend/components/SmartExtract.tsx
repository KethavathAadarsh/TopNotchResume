"use client";
import { useRef, useState } from "react";
import {
  extractSection,
  uploadResume,
  UPLOAD_ACCEPT,
  UPLOAD_MAX_BYTES,
  type SectionType,
} from "@/lib/api";

/** Backend /api/extract rejects anything longer than this. */
const MAX_EXTRACT_CHARS = 30_000;

interface SmartExtractProps {
  section: SectionType;
  label?: string;
  placeholder?: string;
  onExtracted: (data: Record<string, unknown>) => void;
}

const PLACEHOLDERS: Record<SectionType, string> = {
  all: `Paste your entire resume here — LinkedIn export, Word copy-paste, PDF text, or even rough notes.

Example:
John Smith | john@email.com | (555) 123-4567 | San Francisco, CA
linkedin.com/in/john | github.com/johnsmith

Senior Software Engineer at Stripe (Jan 2021 – Present)
• Built payment processing APIs handling $50B+ in transactions
• Led team of 8 engineers...

Skills: Python, Go, React, AWS, Kubernetes...

Education: BS Computer Science, UC Berkeley, 2018`,

  personal: `Paste your contact info — any format works.

Example:
Jane Smith
jane@email.com | (415) 555-0100
San Francisco, CA
linkedin.com/in/jane-smith
github.com/janesmith`,

  experience: `Paste your work history — any format works.

Example:
Senior Software Engineer — Stripe, San Francisco
January 2021 – Present
• Architected payment APIs serving 50M+ requests/day
• Led migration to microservices, cut latency by 40%

Software Engineer — Google, Mountain View
June 2018 – December 2020
• Built data pipelines processing 5TB/day`,

  projects: `Paste your projects — any format works.

Example:
AI Resume Platform (github.com/me/resume-ai)
Tech: Python, FastAPI, LangGraph, Next.js
• Built multi-agent system using LangGraph + GPT-4
• Generates ATS-optimized resumes in under 30 seconds
• 500+ users in first month`,

  skills: `Paste your skills — any format works.

Example:
Languages: Python, Go, TypeScript, Java, SQL
Frameworks: FastAPI, React, gRPC, PyTorch
Cloud: AWS (EC2, S3, Lambda), GCP, Docker, Kubernetes
Databases: PostgreSQL, Redis, BigQuery, MongoDB`,

  education: `Paste your education and certifications — any format works.

Example:
Bachelor of Science in Computer Science
University of California, Berkeley — May 2018
GPA: 3.9/4.0, Magna Cum Laude

AWS Solutions Architect Professional — Amazon (2023)
Google Cloud Professional Data Engineer (2022)`,

  certifications: `Paste your certifications — any format works.

Example:
AWS Solutions Architect Professional (Amazon, 2023)
Google Cloud Professional Data Engineer (2022)
Certified Kubernetes Administrator — CNCF (2021)`,
};

const LABELS: Record<SectionType, string> = {
  all: "Import Full Resume",
  personal: "Extract Personal Info",
  experience: "Extract Work Experience",
  projects: "Extract Projects",
  skills: "Extract Skills",
  education: "Extract Education & Certs",
  certifications: "Extract Certifications",
};

export function SmartExtract({ section, label, placeholder, onExtracted }: SmartExtractProps) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [fileNames, setFileNames] = useState<string[]>([]);
  const [progress, setProgress] = useState({ current: 0, total: 0, name: "" });
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragDepth = useRef(0);

  const busy = loading || uploading;

  function resetMessages() {
    setError("");
    setNotice("");
    setSuccess(false);
  }

  async function runExtract(raw: string) {
    if (!raw.trim()) return;
    setLoading(true);
    setError("");
    setSuccess(false);

    try {
      const result = await extractSection(section, raw);
      onExtracted(result.data);
      setSuccess(true);
      setText("");
      setFileNames([]);
      setNotice("");
      setTimeout(() => {
        setOpen(false);
        setSuccess(false);
      }, 1500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Extraction failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleFiles(files: File[]) {
    if (!files.length) return;
    resetMessages();

    const failures: string[] = [];
    const accepted: { name: string; text: string }[] = [];

    // Reject oversized files up front — no point round-tripping them.
    const toUpload = files.filter(f => {
      if (f.size > UPLOAD_MAX_BYTES) {
        failures.push(`${f.name} (${(f.size / 1_048_576).toFixed(1)} MB — over the 10 MB limit)`);
        return false;
      }
      return true;
    });

    setUploading(true);
    setProgress({ current: 0, total: toUpload.length, name: toUpload[0]?.name ?? "" });

    for (let i = 0; i < toUpload.length; i++) {
      const file = toUpload[i];
      setProgress({ current: i + 1, total: toUpload.length, name: file.name });
      try {
        const { text: extracted } = await uploadResume(file);
        accepted.push({ name: file.name, text: extracted });
      } catch (err: unknown) {
        failures.push(`${file.name} (${err instanceof Error ? err.message : "upload failed"})`);
      }
    }

    setUploading(false);
    setProgress({ current: 0, total: 0, name: "" });

    if (failures.length) {
      setError(
        failures.length === 1
          ? `Couldn't read ${failures[0]}`
          : `Couldn't read ${failures.length} files: ${failures.join("; ")}`
      );
    }

    if (!accepted.length) return;

    // Label each source when more than one chunk of text is in play, so the
    // AI can tell where one document ends and the next begins.
    const existing = text.trim();
    const multiSource = accepted.length > 1 || existing.length > 0;
    const chunks = accepted.map(a =>
      multiSource ? `===== FILE: ${a.name} =====\n${a.text}` : a.text
    );
    let combined = [existing, ...chunks].filter(Boolean).join("\n\n");

    const totalChars = combined.length;
    if (totalChars > MAX_EXTRACT_CHARS) {
      combined = combined.slice(0, MAX_EXTRACT_CHARS);
      setNotice(
        `Read ${totalChars.toLocaleString()} characters — trimmed to the first ${MAX_EXTRACT_CHARS.toLocaleString()} for AI extraction. Review the text below before extracting.`
      );
    }

    setText(combined);
    setFileNames(prev => [...prev, ...accepted.map(a => a.name)]);

    // Don't auto-extract when something failed — let the user see the error
    // and decide, rather than silently extracting a partial set.
    if (!failures.length) await runExtract(combined);
  }

  function onFilePicked(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    // Reset so picking the same file again still fires onChange.
    e.target.value = "";
    void handleFiles(files);
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    if (busy) return;
    void handleFiles(Array.from(e.dataTransfer.files ?? []));
  }

  function onDragEnter(e: React.DragEvent) {
    e.preventDefault();
    dragDepth.current += 1;
    if (!busy) setDragging(true);
  }

  function onDragLeave(e: React.DragEvent) {
    e.preventDefault();
    dragDepth.current -= 1;
    if (dragDepth.current <= 0) {
      dragDepth.current = 0;
      setDragging(false);
    }
  }

  const displayLabel = label || LABELS[section];

  return (
    <div className="mb-5">
      {/* Toggle button */}
      <button
        type="button"
        onClick={() => { setOpen(o => !o); resetMessages(); }}
        className={`w-full flex items-center justify-between px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-medium ${
          open
            ? "bg-brand-500/15 border-brand-500/50 text-brand-400"
            : "bg-[#1a2035] border-[#2a3142] text-slate-400 hover:border-brand-500/40 hover:text-brand-400"
        }`}
      >
        <div className="flex items-center gap-2.5">
          <span className="text-base">✨</span>
          <span>{displayLabel}</span>
          <span className="text-xs bg-brand-500/20 text-brand-400 px-2 py-0.5 rounded-full font-normal">
            AI powered
          </span>
        </div>
        <span className="text-xs text-slate-500">{open ? "▲ collapse" : "▼ expand"}</span>
      </button>

      {/* Expandable panel */}
      {open && (
        <div className="mt-2 card p-4 space-y-3 border-brand-500/20">
          <p className="text-xs text-slate-400 leading-relaxed">
            Upload a resume file or paste raw text — resume copy-paste, LinkedIn export, freeform notes — and AI will extract structured data and fill the form automatically.
          </p>

          {/* File drop zone */}
          <div
            onDrop={onDrop}
            onDragOver={e => e.preventDefault()}
            onDragEnter={onDragEnter}
            onDragLeave={onDragLeave}
            onClick={() => { if (!busy) fileInputRef.current?.click(); }}
            role="button"
            tabIndex={0}
            aria-label="Upload a resume file"
            onKeyDown={e => {
              if ((e.key === "Enter" || e.key === " ") && !busy) {
                e.preventDefault();
                fileInputRef.current?.click();
              }
            }}
            className={`rounded-xl border border-dashed px-4 py-6 text-center transition-all duration-200 ${
              busy ? "cursor-wait opacity-70" : "cursor-pointer"
            } ${
              dragging
                ? "border-brand-500 bg-brand-500/10"
                : "border-[#2a3142] bg-[#141a2c] hover:border-brand-500/50 hover:bg-[#1a2035]"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={UPLOAD_ACCEPT}
              multiple
              onChange={onFilePicked}
              className="hidden"
              disabled={busy}
            />

            {uploading ? (
              <div className="flex items-center justify-center gap-2.5 text-sm text-brand-400">
                <span className="inline-block w-4 h-4 border-2 border-brand-400/30 border-t-brand-400 rounded-full animate-spin" />
                {progress.total > 1
                  ? `Reading ${progress.current} of ${progress.total} — ${progress.name}…`
                  : `Reading ${progress.name || "file"}…`}
              </div>
            ) : (
              <>
                <div className="text-2xl mb-1.5">📄</div>
                <p className="text-sm text-slate-300">
                  <span className="text-brand-400 font-medium">Click to upload</span>
                  <span className="text-slate-500"> or drag &amp; drop</span>
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  PDF, DOCX, TXT or MD — multiple files welcome, up to 10 MB each
                </p>
              </>
            )}
          </div>

          {/* Uploaded file chips */}
          {fileNames.length > 0 && !uploading && (
            <div className="flex flex-wrap gap-2">
              {fileNames.map((name, i) => (
                <span
                  key={`${name}-${i}`}
                  className="inline-flex items-center gap-1.5 text-xs bg-brand-500/10 border border-brand-500/25 text-brand-400 rounded-lg px-2.5 py-1"
                >
                  📄 {name}
                </span>
              ))}
              <button
                type="button"
                onClick={() => { setFileNames([]); setText(""); resetMessages(); }}
                disabled={busy}
                className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-1"
              >
                clear
              </button>
            </div>
          )}

          <div className="flex items-center gap-3">
            <div className="h-px flex-1 bg-[#2a3142]" />
            <span className="text-xs text-slate-600">or paste text</span>
            <div className="h-px flex-1 bg-[#2a3142]" />
          </div>

          <textarea
            className="input-base min-h-[180px] resize-y font-mono text-xs leading-relaxed"
            value={text}
            onChange={e => { setText(e.target.value); resetMessages(); }}
            placeholder={placeholder || PLACEHOLDERS[section]}
            disabled={busy}
          />

          {notice && (
            <p className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
              {notice}
            </p>
          )}

          {error && (
            <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          {success && (
            <p className="text-xs text-green-400 bg-green-500/10 border border-green-500/20 rounded-lg px-3 py-2 flex items-center gap-2">
              <span>✓</span> Extracted successfully — fields have been populated below!
            </p>
          )}

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => void runExtract(text)}
              disabled={busy || !text.trim()}
              className="btn-primary text-sm px-5 disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? (
                <>
                  <span className="inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Extracting…
                </>
              ) : (
                <>✨ Extract & Fill</>
              )}
            </button>
            <button
              type="button"
              onClick={() => { setOpen(false); setText(""); setFileNames([]); resetMessages(); }}
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              Cancel
            </button>
            {text.length > 0 && (
              <span className="text-xs text-slate-600 ml-auto">
                {text.length.toLocaleString()} chars
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
