"use client";

import { useEffect, useState, useCallback } from "react";
import { Lock, AlertTriangle, Download, Copy, FileText } from "lucide-react";
import { getShared, cloneShared, downloadSharedLatex, fetchSharedPdfObjectUrl } from "@/lib/api";
import { PdfViewer } from "@/components/pdf-viewer";

interface SharedResource {
  success: boolean;
  resource_type: string;
  content: Record<string, unknown>;
  allow_download: boolean;
  allow_clone: boolean;
}

export default function SharedResourcePage({
  params,
}: {
  params: { token: string };
}) {
  const [resource, setResource] = useState<SharedResource | null>(null);
  const [error, setError] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [loading, setLoading] = useState(true);
  const [needsPassword, setNeedsPassword] = useState(false);
  const [password, setPassword] = useState("");
  const [actionLoading, setActionLoading] = useState("");
  const [cloneMessage, setCloneMessage] = useState("");
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState("");

  const loadResource = useCallback(
    async (pwd?: string) => {
      setLoading(true);
      setError("");
      setPasswordError("");
      try {
        const res = await getShared(params.token, pwd);
        if (res.success) {
          setResource(res);
          setNeedsPassword(false);
        } else {
          setError("Kunne ikke laste ressursen.");
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Noe gikk galt.";
        if (msg.includes("401") || msg.toLowerCase().includes("password")) {
          setNeedsPassword(true);
        } else if (msg.includes("403") && msg.toLowerCase().includes("incorrect password")) {
          setNeedsPassword(true);
          setPasswordError("Feil passord — prøv igjen.");
        } else if (msg.includes("410")) {
          setError("Denne delingen har utløpt.");
        } else if (msg.includes("404")) {
          setError("Delt lenke ikke funnet.");
        } else {
          setError(msg);
        }
      } finally {
        setLoading(false);
      }
    },
    [params.token]
  );

  useEffect(() => {
    loadResource();
  }, [loadResource]);

  useEffect(() => {
    if (!resource?.content?.full_document) return;
    let revoke: string | null = null;
    setPdfError("");
    fetchSharedPdfObjectUrl(params.token)
      .then((url) => {
        revoke = url;
        setPdfUrl(url);
      })
      .catch((e: unknown) => {
        setPdfError(e instanceof Error ? e.message : "Kunne ikke laste PDF");
      });
    return () => {
      if (revoke) URL.revokeObjectURL(revoke);
    };
  }, [resource, params.token]);

  const handleDownload = () => {
    if (!resource?.content) return;
    downloadSharedLatex(resource.content);
  };

  const handleClone = async () => {
    setActionLoading("clone");
    setCloneMessage("");
    try {
      const res = await cloneShared(params.token, password || undefined);
      if (res.success) {
        setCloneMessage(`Klonet! Ny ressurs-id: ${res.new_resource_id.slice(0, 8)}…`);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Kloning feilet";
      if (msg.includes("401") || msg.includes("403")) {
        setNeedsPassword(true);
        setPasswordError(msg.includes("403") ? "Feil passord for kloning." : "Passord kreves for å klone.");
      } else {
        setError(msg);
      }
    } finally {
      setActionLoading("");
    }
  };

  if (needsPassword) {
    return (
      <div className="max-w-sm mx-auto py-20 text-center">
        <Lock size={32} className="mx-auto mb-4 text-text-muted opacity-40" />
        <h1 className="font-display text-xl mb-2">Passordbeskyttet</h1>
        <p className="text-sm text-text-secondary mb-6">
          Denne ressursen krever passord.
        </p>
        {passwordError && (
          <p className="text-sm text-accent-red mb-3" role="alert">
            {passwordError}
          </p>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            loadResource(password);
          }}
          className="space-y-3"
        >
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Skriv inn passord..."
            className="input text-center"
            autoFocus
          />
          <button type="submit" className="btn-primary w-full">
            Åpne
          </button>
        </form>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-2 border-accent-blue border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-sm mx-auto py-20 text-center">
        <AlertTriangle size={32} className="mx-auto mb-4 text-accent-red opacity-60" />
        <h1 className="font-display text-xl mb-2">Feil</h1>
        <p className="text-sm text-text-secondary" role="alert">
          {error}
        </p>
      </div>
    );
  }

  if (!resource) return null;

  return (
    <div className="max-w-reading mx-auto">
      <div className="card mb-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-lg font-semibold flex items-center gap-2">
              <FileText size={18} className="text-text-muted" />
              Delt ressurs
            </h1>
            <p className="text-sm text-text-secondary mt-1">
              Type: {resource.resource_type}
            </p>
            {cloneMessage && (
              <p className="text-xs text-accent-green mt-2">{cloneMessage}</p>
            )}
          </div>
          <div className="flex gap-2">
            {resource.allow_download && (
              <button type="button" onClick={handleDownload} className="btn-secondary">
                <Download size={14} /> LaTeX
              </button>
            )}
            {resource.allow_clone && (
              <button
                type="button"
                onClick={handleClone}
                disabled={actionLoading === "clone"}
                className="btn-secondary"
              >
                <Copy size={14} />
                {actionLoading === "clone" ? "Kloner…" : "Klon"}
              </button>
            )}
          </div>
        </div>
      </div>

      {pdfUrl ? (
        <div className="card !p-0 overflow-hidden mb-6">
          <PdfViewer src={pdfUrl} title="Delt PDF" />
        </div>
      ) : pdfError ? (
        <p className="text-sm text-text-secondary mb-4">{pdfError}</p>
      ) : (
        <p className="text-sm text-text-muted mb-4">Laster PDF-forhåndsvisning…</p>
      )}

      <details className="card">
        <summary className="text-sm font-medium cursor-pointer">Vis LaTeX-kilde</summary>
        <pre className="text-xs font-mono whitespace-pre-wrap text-text-secondary max-h-[40vh] overflow-y-auto mt-3">
          {String(resource.content.full_document || JSON.stringify(resource.content, null, 2))}
        </pre>
      </details>
    </div>
  );
}
