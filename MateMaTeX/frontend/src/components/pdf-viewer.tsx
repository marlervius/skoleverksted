"use client";

import { useEffect, useState } from "react";
import { ZoomIn, ZoomOut } from "lucide-react";

interface PdfViewerProps {
  src: string;
  title?: string;
  className?: string;
}

/** PDF preview with zoom — works with blob/data URLs and job PDF proxy. */
export function PdfViewer({ src, title = "PDF-forhåndsvisning", className = "" }: PdfViewerProps) {
  const [zoom, setZoom] = useState(100);

  useEffect(() => {
    setZoom(100);
  }, [src]);

  if (!src) return null;

  const iframeSrc = src.startsWith("data:") ? src : src;

  return (
    <div className={`flex flex-col ${className}`}>
      <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-border bg-surface-elevated/50 text-xs">
        <span className="text-text-muted truncate">{title}</span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            className="btn-ghost !p-1.5"
            aria-label="Zoom ut"
            onClick={() => setZoom((z) => Math.max(60, z - 10))}
          >
            <ZoomOut size={14} />
          </button>
          <span className="w-10 text-center tabular-nums">{zoom}%</span>
          <button
            type="button"
            className="btn-ghost !p-1.5"
            aria-label="Zoom inn"
            onClick={() => setZoom((z) => Math.min(160, z + 10))}
          >
            <ZoomIn size={14} />
          </button>
        </div>
      </div>
      <div className="overflow-auto bg-neutral-200/40">
        <iframe
          title={title}
          src={iframeSrc}
          className="w-full min-h-[520px] border-0 bg-white"
          style={{
            transform: `scale(${zoom / 100})`,
            transformOrigin: "top center",
            height: `${Math.round(520 * (100 / zoom))}px`,
          }}
        />
      </div>
    </div>
  );
}
