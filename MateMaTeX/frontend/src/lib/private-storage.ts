const PRIVATE_SESSION_KEY = "skoleverksted_private_session";
const DEFAULT_MAX_AGE = 7 * 24 * 60 * 60 * 1000;

type StoredValue<T> = { value: T; savedAt: number };

export function isPrivateSession(): boolean {
  if (typeof window === "undefined") return false;
  return sessionStorage.getItem(PRIVATE_SESSION_KEY) === "1";
}

export function setPrivateSession(enabled: boolean): void {
  if (typeof window === "undefined") return;
  if (enabled) sessionStorage.setItem(PRIVATE_SESSION_KEY, "1");
  else sessionStorage.removeItem(PRIVATE_SESSION_KEY);
}

export function saveLocal<T>(key: string, value: T): void {
  if (typeof window === "undefined" || isPrivateSession()) return;
  localStorage.setItem(key, JSON.stringify({ value, savedAt: Date.now() } satisfies StoredValue<T>));
}

export function loadLocal<T>(key: string, maxAgeMs = DEFAULT_MAX_AGE): T | null {
  if (typeof window === "undefined" || isPrivateSession()) return null;
  const raw = localStorage.getItem(key);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as StoredValue<T> | T;
    if (parsed && typeof parsed === "object" && "savedAt" in parsed && "value" in parsed) {
      if (Date.now() - Number(parsed.savedAt) > maxAgeMs) {
        localStorage.removeItem(key);
        return null;
      }
      return parsed.value;
    }
    return parsed as T; // Backward compatibility; rewritten on next save.
  } catch {
    localStorage.removeItem(key);
    return null;
  }
}

export function clearSkoleverkstedStorage(): number {
  if (typeof window === "undefined") return 0;
  const keys = Object.keys(localStorage).filter((key) =>
    key.startsWith("skoleverksted_") || key.startsWith("vgs_ki_") || key.startsWith("vgs-") || key.startsWith("fov_") || key.startsWith("matematex_") || key.startsWith("matematex-")
  );
  keys.forEach((key) => localStorage.removeItem(key));
  return keys.length;
}
