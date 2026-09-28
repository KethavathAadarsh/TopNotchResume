"use client";

interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  tagline: string;
  description: string;
  speed: 1 | 2 | 3 | 4 | 5;   // 5 = fastest
  cost: 1 | 2 | 3 | 4 | 5;    // 5 = cheapest
  badge?: "default" | "recommended" | "powerful";
}

// Keep in sync with SUPPORTED_MODELS in backend/app/utils/claude_client.py.
// Only models supporting both structured outputs and adaptive thinking belong
// here — the backend rejects anything else and falls back to its default.
const MODELS: ModelInfo[] = [
  {
    id: "claude-sonnet-5",
    name: "Claude Sonnet 5",
    provider: "Anthropic",
    tagline: "Fast · Most economical",
    description: "Near-Opus quality on writing and structured extraction at a fraction of the cost. Great for quick iterations and straightforward profiles.",
    speed: 5,
    cost: 5,
    badge: "recommended",
  },
  {
    id: "claude-opus-4-8",
    name: "Claude Opus 4.8",
    provider: "Anthropic",
    tagline: "High quality · Balanced cost",
    description: "Previous-generation flagship. Clear, warm prose and strong reasoning — a solid pick when you want Opus-tier output at steady latency.",
    speed: 4,
    cost: 3,
  },
  {
    id: "claude-opus-5",
    name: "Claude Opus 5",
    provider: "Anthropic",
    tagline: "Best overall · Recommended default",
    description: "Deep reasoning with adaptive thinking, so it decides how hard to think per section. Best bullet quality and JD alignment for the 5-agent pipeline.",
    speed: 3,
    cost: 2,
    badge: "default",
  },
  {
    id: "claude-fable-5",
    name: "Claude Fable 5",
    provider: "Anthropic",
    tagline: "Most capable · Premium",
    description: "Anthropic's most capable model — worth it for executive and highly technical roles. Costs roughly 2× Opus 5 and takes noticeably longer.",
    speed: 2,
    cost: 1,
    badge: "powerful",
  },
];

function Dots({ filled, total, color }: { filled: number; total: number; color: string }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`w-1.5 h-1.5 rounded-full ${i < filled ? color : "bg-border"}`}
        />
      ))}
    </div>
  );
}

const BADGE_STYLE: Record<string, string> = {
  default:     "bg-slate-700 text-slate-300 border-slate-600",
  recommended: "bg-brand-500/20 text-brand-400 border-brand-500/40",
  powerful:    "bg-purple-500/20 text-purple-400 border-purple-500/40",
};
const BADGE_LABEL: Record<string, string> = {
  default:     "Default",
  recommended: "Recommended",
  powerful:    "Powerful",
};

interface Props {
  isOpen: boolean;
  selectedModel: string;
  onSelect: (modelId: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
  confirmLabel?: string;
}

export function ModelSelectorModal({
  isOpen, selectedModel, onSelect, onConfirm, onCancel, confirmLabel = "Start Generation →",
}: Props) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onCancel}
      />

      {/* Modal */}
      <div className="relative w-full max-w-lg bg-surface border border-border rounded-2xl shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-border">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-lg">🤖</span>
            <h2 className="text-base font-bold text-white">Select AI Model</h2>
          </div>
          <p className="text-xs text-slate-500">
            Choose the model powering your JARVIS 5-agent pipeline. API key stays the same.
          </p>
        </div>

        {/* Model list */}
        <div className="overflow-y-auto flex-1 px-4 py-3 space-y-2">
          {MODELS.map((m) => {
            const isSelected = selectedModel === m.id;
            return (
              <button
                key={m.id}
                onClick={() => onSelect(m.id)}
                className={`w-full text-left rounded-xl border p-4 transition-all duration-150 ${
                  isSelected
                    ? "border-brand-500/60 bg-brand-500/8 ring-1 ring-brand-500/30"
                    : "border-border hover:border-slate-600 hover:bg-white/2"
                }`}
              >
                <div className="flex items-start gap-3">
                  {/* Radio dot */}
                  <div className={`mt-0.5 w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center transition-colors ${
                    isSelected ? "border-brand-500 bg-brand-500" : "border-slate-600"
                  }`}>
                    {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                  </div>

                  <div className="flex-1 min-w-0">
                    {/* Name row */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-white">{m.name}</span>
                      <span className="text-[10px] text-slate-600">{m.provider}</span>
                      {m.badge && (
                        <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full border ${BADGE_STYLE[m.badge]}`}>
                          {BADGE_LABEL[m.badge]}
                        </span>
                      )}
                    </div>

                    {/* Tagline */}
                    <p className="text-xs text-slate-400 mt-0.5">{m.tagline}</p>

                    {/* Description */}
                    <p className="text-[11px] text-slate-500 mt-1.5 leading-relaxed">{m.description}</p>

                    {/* Speed / cost bars */}
                    <div className="flex items-center gap-4 mt-2.5">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] text-slate-600 uppercase tracking-wide">Speed</span>
                        <Dots filled={m.speed} total={5} color="bg-green-500" />
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] text-slate-600 uppercase tracking-wide">Economy</span>
                        <Dots filled={m.cost} total={5} color="bg-brand-500" />
                      </div>
                    </div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-border flex items-center justify-between gap-3">
          <button
            onClick={onCancel}
            className="btn-secondary text-sm px-4 py-2"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="btn-primary text-sm px-6 py-2 flex items-center gap-2"
          >
            <span>{confirmLabel}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
