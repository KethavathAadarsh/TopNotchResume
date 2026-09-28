export interface ExperienceEntry {
  company: string;
  title: string;
  start_date: string;
  end_date: string;
  location?: string;
  bullets: string[];
}

export interface ProjectEntry {
  name: string;
  description: string;
  technologies: string[];
  bullets: string[];
  url?: string;
  github_url?: string;
}

export interface EducationEntry {
  institution: string;
  degree: string;
  field: string;
  graduation_date: string;
  gpa?: string;
  honors?: string;
}

export interface CertificationEntry {
  name: string;
  issuer: string;
  date?: string;
}

export interface SkillCategory {
  category: string;
  items: string[];
}

export interface CandidateProfile {
  name: string;
  email: string;
  phone?: string;
  location?: string;
  linkedin?: string;
  github?: string;
  website?: string;
  summary?: string;
  experience: ExperienceEntry[];
  projects: ProjectEntry[];
  skill_categories: SkillCategory[];
  flat_skills: string[];
  education: EducationEntry[];
  certifications: CertificationEntry[];
  awards: string[];
  publications: string[];
}

export type ResumeFormat = "ats" | "executive" | "swe" | "startup" | "minimal" | "research";

export interface GenerateRequest {
  profile: CandidateProfile;
  job_description: string;
  format: ResumeFormat;
  max_pages: 1 | 2;
  target_role?: string;
  model?: string;
}

export interface GenerateResponse {
  download_id: string;
  session_id?: string;
  ats_score: number;
  keywords_matched: string[];
  keywords_missing: string[];
  sections_included: string[];
  generation_time_ms: number;
}

export const EMPTY_PROFILE: CandidateProfile = {
  name: "",
  email: "",
  phone: "",
  location: "",
  linkedin: "",
  github: "",
  website: "",
  summary: "",
  experience: [],
  projects: [],
  skill_categories: [],
  flat_skills: [],
  education: [],
  certifications: [],
  awards: [],
  publications: [],
};

export const RESUME_FORMAT_LABELS: Record<ResumeFormat, string> = {
  ats: "ATS Optimized",
  executive: "Executive",
  swe: "Software Engineer",
  startup: "Startup",
  minimal: "Minimal",
  research: "Research",
};
