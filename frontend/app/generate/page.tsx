"use client";
import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ResumeWizard } from "@/components/ResumeWizard";

// Read ?restore= on the client so the page works as a static export on GitHub Pages
function Wizard() {
  const restoreId = useSearchParams().get("restore") ?? undefined;
  return <ResumeWizard restoreId={restoreId} />;
}

export default function GeneratePage() {
  return (
    <div className="min-h-screen bg-surface">
      <nav className="border-b border-border px-6 py-4 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
          <span className="text-base font-bold text-white">TopNotch</span>
          <span className="text-base font-bold text-brand-500">Resume</span>
        </Link>
        <span className="text-xs text-slate-600">JARVIS Multi-Agent Platform</span>
      </nav>

      <Suspense fallback={null}>
        <Wizard />
      </Suspense>
    </div>
  );
}
