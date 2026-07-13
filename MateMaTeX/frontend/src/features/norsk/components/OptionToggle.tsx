"use client";

import { Check } from "lucide-react";

export function OptionToggle({
  label,
  checked,
  onChange,
  disabled,
  description,
  highlight = false,
  advanced = false,
}: {
  label: string;
  checked: boolean;
  onChange: (val: boolean) => void;
  disabled?: boolean;
  description?: string;
  highlight?: boolean;
  advanced?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={() => !disabled && onChange(!checked)}
      className={`
        flex items-center justify-between p-3 rounded-xl border transition-all duration-200
        ${
          checked
            ? highlight
              ? "bg-emerald-500/10 border-emerald-500/50 text-emerald-100"
              : advanced
                ? "bg-amber-500/10 border-amber-500/50 text-amber-100"
                : "bg-blue-500/10 border-blue-500/50 text-blue-100"
            : "bg-slate-900/50 border-slate-700/50 text-slate-400 opacity-60 hover:opacity-100"
        }
        ${disabled ? "cursor-not-allowed" : "cursor-pointer"}
      `}
      disabled={disabled}
    >
      <div className="flex flex-col items-start">
        <span className="text-xs font-medium leading-none">{label}</span>
        {description && (
          <span className="text-[10px] text-slate-500 mt-1">{description}</span>
        )}
      </div>
      <div
        className={`
        w-5 h-5 rounded-md flex items-center justify-center transition-colors
        ${
          checked
            ? highlight
              ? "bg-emerald-500 text-white"
              : advanced
                ? "bg-amber-500 text-white"
                : "bg-blue-500 text-white"
            : "bg-slate-800 border border-slate-600"
        }
      `}
      >
        {checked && <Check className="w-3.5 h-3.5 stroke-[3]" />}
      </div>
    </button>
  );
}
