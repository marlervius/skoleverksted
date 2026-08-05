"use client";

import type { ReactNode } from "react";

type Block =
  | { type: "heading"; level: number; text: string }
  | { type: "paragraph"; text: string }
  | { type: "ul" | "ol"; items: string[] }
  | { type: "quote"; text: string }
  | { type: "code"; text: string }
  | { type: "table"; headers: string[]; rows: string[][] };

const tableDivider = /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/;

function splitTableRow(line: string) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
}

function isTableStart(lines: string[], index: number) {
  return Boolean(lines[index]?.includes("|") && lines[index + 1] && tableDivider.test(lines[index + 1]));
}

/** Parse the safe Markdown subset produced by the content agents without rendering raw HTML. */
export function parseMarkdownBlocks(markdown: string): Block[] {
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    if (line.trim().startsWith("```")) {
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        code.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      blocks.push({ type: "code", text: code.join("\n") });
      continue;
    }

    const heading = line.match(/^\s*(#{1,6})\s+(.+?)\s*#*\s*$/);
    if (heading) {
      blocks.push({ type: "heading", level: heading[1].length, text: heading[2] });
      index += 1;
      continue;
    }

    if (isTableStart(lines, index)) {
      const headers = splitTableRow(lines[index]);
      index += 2;
      const rows: string[][] = [];
      while (index < lines.length && lines[index].trim() && lines[index].includes("|")) {
        rows.push(splitTableRow(lines[index]));
        index += 1;
      }
      blocks.push({ type: "table", headers, rows });
      continue;
    }

    const listMatch = line.match(/^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+)$/);
    if (listMatch) {
      const ordered = /^\s*\d+[.)]\s+/.test(line);
      const items: string[] = [];
      while (index < lines.length) {
        const item = lines[index].match(ordered ? /^\s*\d+[.)]\s+(.+)$/ : /^\s*[-*+]\s+(.+)$/);
        if (!item) break;
        items.push(item[1]);
        index += 1;
      }
      blocks.push({ type: ordered ? "ol" : "ul", items });
      continue;
    }

    if (/^\s*>\s?/.test(line)) {
      const quote: string[] = [];
      while (index < lines.length && /^\s*>\s?/.test(lines[index])) {
        quote.push(lines[index].replace(/^\s*>\s?/, ""));
        index += 1;
      }
      blocks.push({ type: "quote", text: quote.join(" ") });
      continue;
    }

    const paragraph: string[] = [line.trim()];
    index += 1;
    while (index < lines.length && lines[index].trim() && !/^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+|>\s?|```)/.test(lines[index]) && !isTableStart(lines, index)) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push({ type: "paragraph", text: paragraph.join(" ") });
  }

  return blocks;
}

function safeHref(value: string) {
  if (!/^https:\/\//i.test(value.trim())) return null;
  try {
    const url = new URL(value);
    if (["http:", "https:"].includes(url.protocol)) return url.href;
  } catch {
    // Invalid links are shown as plain text.
  }
  return null;
}

function inlineText(value: string): ReactNode[] {
  const tokens = value.split(/(\[[^\]]+\]\([^\s)]+\)|\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g).filter(Boolean);
  return tokens.map((token, index) => {
    const link = token.match(/^\[([^\]]+)\]\(([^\s)]+)\)$/);
    if (link) {
      const href = safeHref(link[2]);
      return href ? <a key={index} href={href} target="_blank" rel="noreferrer" className="font-medium text-accent-blue underline underline-offset-2">{link[1]}</a> : <span key={index}>{token}</span>;
    }
    if (token.startsWith("**") && token.endsWith("**")) return <strong key={index}>{token.slice(2, -2)}</strong>;
    if (token.startsWith("`") && token.endsWith("`")) return <code key={index} className="rounded bg-surface-elevated px-1 py-0.5 font-mono text-[0.9em]">{token.slice(1, -1)}</code>;
    if (token.startsWith("*") && token.endsWith("*")) return <em key={index}>{token.slice(1, -1)}</em>;
    return <span key={index}>{token}</span>;
  });
}

export function MarkdownPreview({ markdown, className = "" }: { markdown: string; className?: string }) {
  const blocks = parseMarkdownBlocks(markdown);
  return (
    <div className={`prose prose-stone max-w-none text-sm leading-7 text-text-secondary ${className}`}>
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          const Tag = (`h${Math.min(6, block.level)}`) as keyof JSX.IntrinsicElements;
          return <Tag key={index} className="mt-5 scroll-mt-24 font-display text-text-primary first:mt-0">{inlineText(block.text)}</Tag>;
        }
        if (block.type === "ul" || block.type === "ol") {
          const Tag = block.type;
          return <Tag key={index} className="my-3 space-y-1 pl-6 marker:text-accent-teal">{block.items.map((item, itemIndex) => <li key={itemIndex}>{inlineText(item)}</li>)}</Tag>;
        }
        if (block.type === "quote") return <blockquote key={index} className="my-4 border-l-4 border-accent-teal/40 bg-accent-teal/5 px-4 py-2 italic">{inlineText(block.text)}</blockquote>;
        if (block.type === "code") return <pre key={index} className="my-4 overflow-x-auto rounded-lg bg-stone-900 p-4 text-xs leading-6 text-stone-100"><code>{block.text}</code></pre>;
        if (block.type === "table") return <div key={index} className="my-4 overflow-x-auto rounded-lg border border-border"><table className="min-w-full border-collapse text-left text-xs"><thead className="bg-surface-elevated"><tr>{block.headers.map((header, headerIndex) => <th key={headerIndex} className="border-b border-border px-3 py-2 font-semibold text-text-primary">{inlineText(header)}</th>)}</tr></thead><tbody>{block.rows.map((row, rowIndex) => <tr key={rowIndex} className="odd:bg-surface/60">{block.headers.map((_, cellIndex) => <td key={cellIndex} className="border-b border-border px-3 py-2 align-top">{inlineText(row[cellIndex] ?? "")}</td>)}</tr>)}</tbody></table></div>;
        if (block.type === "paragraph") return <p key={index} className="my-3">{inlineText(block.text)}</p>;
        return null;
      })}
    </div>
  );
}
