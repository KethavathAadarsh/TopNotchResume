import Link from "next/link";

const FEATURES = [
  {
    icon: "🧠",
    title: "Parallel AI Pipeline",
    desc: "JARVIS v2 runs Profile + JD agents simultaneously via asyncio.gather, cutting generation time 30%. Semantic embeddings pre-score alignment before GPT analysis.",
  },
  {
    icon: "🎯",
    title: "Semantic Skill Matching",
    desc: "OpenAI text-embedding-3-small vectors score every candidate skill against JD requirements. Cosine similarity finds matches that exact keyword search misses.",
  },
  {
    icon: "✍️",
    title: "Human-Quality Writing",
    desc: "GPT-4o-mini rewrites every bullet using the CAR framework — measurable impact, strong action verbs, natural ATS keyword injection.",
  },
  {
    icon: "🎨",
    title: "6 Format Themes",
    desc: "ATS, Executive (Georgia/Navy), SWE (Teal accent), Startup (Indigo bar), Minimal (gray palette), Research (Times New Roman). Each theme is a distinct visual identity.",
  },
  {
    icon: "⚡",
    title: "Live Pipeline Streaming",
    desc: "Server-Sent Events stream real agent progress to the browser — watch each step complete in real time, not a fake animation.",
  },
  {
    icon: "📋",
    title: "Cover Letter + History",
    desc: "One-click AI cover letter generation tailored to the same job. Full generation history dashboard with ATS scores, download links, and format tracking.",
  },
];

const STEPS = [
  { num: "01", label: "Paste your profile" },
  { num: "02", label: "Add the job description" },
  { num: "03", label: "JARVIS generates" },
  { num: "04", label: "Download your resume" },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-surface">
      {/* Nav */}
      <nav className="border-b border-border px-6 py-4 flex items-center justify-between max-w-7xl mx-auto">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-white tracking-tight">TopNotch</span>
          <span className="text-lg font-bold text-brand-500">Resume</span>
          <span className="text-xs text-slate-600 ml-2 border border-border rounded-full px-2 py-0.5">v2</span>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/history" className="text-sm text-slate-400 hover:text-white transition-colors">
            History
          </Link>
          <Link href="/generate" className="btn-primary text-sm">
            Build My Resume
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative max-w-5xl mx-auto px-6 pt-24 pb-20 text-center bg-hero-gradient">
        <div className="inline-flex items-center gap-2 bg-brand-500/10 border border-brand-500/30 rounded-full px-4 py-1.5 text-xs text-brand-500 font-medium mb-8">
          Powered by GPT-4o-mini + LangGraph · v2 — Phase 2/3/4 Active
        </div>
        <h1 className="text-5xl md:text-6xl font-bold text-white leading-tight tracking-tight mb-6">
          Your resume, optimized by <br />
          <span className="text-brand-500">enterprise AI</span>
        </h1>
        <p className="text-lg text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
          Not a template engine. A multi-agent intelligence platform that semantically understands
          your profile, interprets job descriptions, and generates ATS-optimized resumes with
          human-quality writing.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link href="/generate" className="btn-primary text-base px-8 py-3">
            Generate My Resume →
          </Link>
          <a
            href="https://github.com"
            className="btn-secondary text-base px-8 py-3"
            target="_blank"
            rel="noopener noreferrer"
          >
            View on GitHub
          </a>
        </div>
      </section>

      {/* How it works */}
      <section className="max-w-4xl mx-auto px-6 py-16">
        <h2 className="text-2xl font-bold text-white text-center mb-12">How it works</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {STEPS.map((step, i) => (
            <div key={step.num} className="flex flex-col items-center text-center">
              <div className="w-12 h-12 rounded-full bg-brand-500/10 border border-brand-500/30 flex items-center justify-center text-brand-500 font-bold text-sm mb-3">
                {step.num}
              </div>
              <p className="text-sm text-slate-300 font-medium">{step.label}</p>
              {i < STEPS.length - 1 && (
                <div className="hidden md:block absolute mt-6 ml-24 text-border text-xl">→</div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <h2 className="text-2xl font-bold text-white text-center mb-3">
          Built different from every resume builder
        </h2>
        <p className="text-slate-400 text-center mb-12">
          The moat is semantic intelligence — not GPT wrapper templates.
        </p>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f) => (
            <div key={f.title} className="card p-6 hover:border-brand-500/40 transition-colors duration-200">
              <div className="text-2xl mb-3">{f.icon}</div>
              <h3 className="font-semibold text-white mb-2">{f.title}</h3>
              <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-2xl mx-auto px-6 py-20 text-center">
        <h2 className="text-3xl font-bold text-white mb-4">Ready to stand out?</h2>
        <p className="text-slate-400 mb-8">
          Takes 5 minutes. Generates a tailored, ATS-optimized resume for any job.
        </p>
        <Link href="/generate" className="btn-primary text-base px-10 py-3 inline-block">
          Build My Resume — Free
        </Link>
      </section>

      {/* Footer */}
      <footer className="border-t border-border px-6 py-6 text-center text-xs text-slate-600 space-y-1">
        <div>TopNotchResume · Enterprise AI Resume Platform · v2.0</div>
        <div className="flex items-center justify-center gap-4">
          <Link href="/generate" className="hover:text-slate-400 transition-colors">Build Resume</Link>
          <Link href="/history" className="hover:text-slate-400 transition-colors">History</Link>
          <a href="/docs/architecture.html" className="hover:text-slate-400 transition-colors">Architecture</a>
        </div>
      </footer>
    </div>
  );
}
