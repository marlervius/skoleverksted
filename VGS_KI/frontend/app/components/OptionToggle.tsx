"use client";

import React from "react";

interface OptionToggleProps {
  label: string;
  checked: boolean;
  onChange: (val: boolean) => void;
  disabled?: boolean;
  description?: string;
}

function OptionToggleInner({
  label,
  checked,
  onChange,
  disabled,
  description,
}: OptionToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={`${label}${description ? ` - ${description}` : ""}`}
      onClick={() => !disabled && onChange(!checked)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          if (!disabled) onChange(!checked);
        }
      }}
      className={`
        flex items-center justify-between gap-3 px-3 py-2.5 rounded-md border text-left transition-colors
        focus:outline-none focus:ring-2 focus:ring-accent-600/30
        ${
          checked
            ? "bg-accent-50 border-accent-200"
            : "bg-white border-stone-200 hover:border-stone-300"
        }
        ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"}
      `}
      disabled={disabled}
    >
      <div className="flex flex-col items-start min-w-0">
        <span className={`text-xs font-medium leading-tight ${checked ? "text-accent-800" : "text-stone-700"}`}>
          {label}
        </span>
        {description && (
          <span className="text-[10px] text-stone-400 mt-0.5 leading-tight">{description}</span>
        )}
      </div>
      {/* Switch */}
      <span
        className={`relative shrink-0 w-9 h-5 rounded-full transition-colors ${
          checked ? "bg-accent-600" : "bg-stone-300"
        }`}
        aria-hidden="true"
      >
        <span
          className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-transform ${
            checked ? "translate-x-4" : "translate-x-0"
          }`}
        />
      </span>
    </button>
  );
}

export const OptionToggle = React.memo(OptionToggleInner);
