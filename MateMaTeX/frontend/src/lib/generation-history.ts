/**
 * Lokal historikk og favoritter (localStorage). Fungerer uten PostgreSQL.
 */

import type { GenerationRequest } from "@/lib/store";
import { loadLocal, saveLocal } from "@/lib/private-storage";

const HISTORY_KEY = "matematex_history_v1";
const MAX_ENTRIES = 40;

export interface HistoryEntry {
  jobId: string;
  createdAt: string;
  topic: string;
  grade: string;
  materialType: string;
  favorite: boolean;
  status?: "completed" | "completed_with_warnings" | "failed";
  warningReason?: string;
  /** Full kopi av skjema for «Lag lignende» og visning */
  request: GenerationRequest;
}

function readRaw(): HistoryEntry[] {
  if (typeof window === "undefined") return [];
  const parsed = loadLocal<HistoryEntry[]>(HISTORY_KEY);
  return Array.isArray(parsed) ? parsed : [];
}

function writeRaw(entries: HistoryEntry[]) {
  if (typeof window === "undefined") return;
  try {
    saveLocal(HISTORY_KEY, entries.slice(0, MAX_ENTRIES));
  } catch {
    /* quota */
  }
}

export function listHistory(): HistoryEntry[] {
  return readRaw();
}

export function appendHistory(entry: HistoryEntry): void {
  const cur = readRaw().filter((e) => e.jobId !== entry.jobId);
  cur.unshift(entry);
  writeRaw(cur);
}

export function updateHistoryFavorite(jobId: string, favorite: boolean): void {
  const cur = readRaw().map((e) =>
    e.jobId === jobId ? { ...e, favorite } : e
  );
  writeRaw(cur);
}

export function removeHistoryEntry(jobId: string): void {
  writeRaw(readRaw().filter((e) => e.jobId !== jobId));
}

export function isJobFavorite(jobId: string): boolean {
  return readRaw().some((e) => e.jobId === jobId && e.favorite);
}
