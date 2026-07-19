"use client";

import type { Dispatch, SetStateAction } from "react";
import { ChevronDown, ChevronUp, History } from "lucide-react";
import type { HistoryItem } from "../lib/fovTypes";
import { summarizeHistoryMeta } from "../lib/fovHistory";

export function HistoryPanel({
  history,
  showHistory,
  setShowHistory,
  onSelect,
  onClear,
}: {
  history: HistoryItem[];
  showHistory: boolean;
  setShowHistory: Dispatch<SetStateAction<boolean>>;
  onSelect: (item: HistoryItem) => void;
  onClear: () => void;
}) {
  if (history.length === 0) return null;

  return (
    <div className="mb-4">
      <button
        type="button"
        onClick={() => setShowHistory((v) => !v)}
        className="flex items-center gap-2 text-stone-500 hover:text-stone-700 text-sm transition-colors"
      >
        <History className="w-4 h-4" />
        <span>Tidligere leksjoner ({history.length})</span>
        {showHistory ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {showHistory && (
        <div className="mt-2 bg-white border border-stone-200 rounded-lg shadow-card overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 border-b border-stone-200">
            <span className="text-xs text-stone-400">Klikk for å fylle inn skjemaet</span>
            <button
              type="button"
              onClick={onClear}
              className="text-xs text-red-600 hover:text-red-700 transition-colors"
            >
              Slett historikk
            </button>
          </div>
          <div className="max-h-52 overflow-y-auto divide-y divide-stone-100">
            {history.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelect(item)}
                className="w-full text-left px-4 py-3 hover:bg-stone-50 transition-colors group"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm text-stone-800 font-medium truncate group-hover:text-stone-900">
                      {item.topic}
                    </p>
                    <p className="text-xs text-stone-500 mt-0.5">
                      {item.subject} ·{" "}
                      {item.multiLevels && item.multiLevels.length >= 2
                        ? `${item.multiLevels.join(", ")} (flernivå)`
                        : item.level}
                    </p>
                    <p className="text-[11px] text-stone-400 mt-1 line-clamp-2">
                      {summarizeHistoryMeta(item)}
                    </p>
                  </div>
                  <span className="text-xs text-stone-400 shrink-0 pt-0.5">
                    {new Date(item.timestamp).toLocaleDateString("nb-NO")}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
