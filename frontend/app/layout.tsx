import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TopNotchResume — AI-Powered Resume Intelligence",
  description:
    "Generate enterprise-grade, ATS-optimized resumes powered by multi-agent AI. Tailored to every job description.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-surface antialiased">{children}</body>
    </html>
  );
}
