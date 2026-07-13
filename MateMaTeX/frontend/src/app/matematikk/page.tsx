"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useAppStore } from "@/lib/store";
import { GenerationWizard } from "@/components/generation-wizard";
import { PipelineProgress } from "@/components/pipeline-progress";
import { ResultView } from "@/components/result-view";
import { TrustSignals } from "@/components/trust-signals";
import { M1CoverageCard } from "@/components/m1-coverage";
import { LatexEditor } from "@/components/latex-editor";
import {
  compileLatex,
  createGenerationVersion,
  verifyLatex,
} from "@/lib/api";

export default function HomePage() {
  const isGenerating = useAppStore((s) => s.isGenerating);
  const result = useAppStore((s) => s.result);
  const showLatexEditor = useAppStore((s) => s.showLatexEditor);
  const toggleLatexEditor = useAppStore((s) => s.toggleLatexEditor);

  // Full-screen LaTeX editor (opened from result view)
  if (showLatexEditor && result?.fullDocument) {
    return (
      <div className="fixed inset-0 z-40 bg-bg flex flex-col">
        <LatexEditor
          initialContent={result.fullDocument}
          onSave={async (content) => {
            const verification = await verifyLatex(content);
            if (verification.claims_incorrect > 0) {
              throw new Error(
                `Lagring blokkert: SymPy fant ${verification.claims_incorrect} feil i fasiten.`
              );
            }
            const compiled = await compileLatex(content, `edited-${result.jobId.slice(0, 8)}`);
            if (!compiled.success) {
              throw new Error("Lagring blokkert: Dokumentet kompilerer ikke til PDF.");
            }
            await createGenerationVersion(result.jobId, content);
            const mapClaim = (claim: Record<string, unknown>) => ({
              claimId: String(claim.claim_id ?? ""),
              latexExpression: String(claim.latex_expression ?? ""),
              claimType: String(claim.claim_type ?? ""),
              context: String(claim.context ?? ""),
              isCorrect: (claim.is_correct ?? null) as boolean | null,
              errorMessage: String(claim.error_message ?? ""),
              expectedResult: String(claim.expected_result ?? ""),
              actualResult: String(claim.actual_result ?? ""),
            });
            useAppStore.getState().setResult({
              ...result,
              fullDocument: content,
              pdfBase64: compiled.pdf_base64,
              latexCompiled: true,
              status:
                verification.claims_unparseable > 0
                  ? "completed_with_warnings"
                  : "completed",
              warningReason:
                verification.claims_unparseable > 0 ? "unparseable" : "",
              mathVerification: {
                claimsChecked: verification.claims_checked,
                claimsCorrect: verification.claims_correct,
                claimsIncorrect: verification.claims_incorrect,
                claimsUnparseable: verification.claims_unparseable,
                allCorrect: verification.all_correct,
                summary: verification.summary,
                incorrectClaims: verification.errors.map(mapClaim),
                unparseableClaims: verification.unparseable_claims.map(mapClaim),
              },
            });
          }}
          onClose={toggleLatexEditor}
        />
      </div>
    );
  }

  return (
    <div>
      <AnimatePresence mode="wait">
        {/* State 1: Generation wizard */}
        {!isGenerating && !result && (
          <motion.div
            key="wizard"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.25 }}
          >
            <div className="text-center mb-10 pt-4">
              <h1 className="font-display text-4xl tracking-tight mb-2">
                Hva skal vi lage i dag?
              </h1>
              <p className="text-text-secondary">
                LK20-tilpasset matte med SymPy-verifisert fasit — levert som PDF du eier
              </p>
              <p className="text-xs text-text-muted mt-2">
                Ingen elevdata.{" "}
                <a href="/personvern" className="text-accent-blue hover:underline">
                  Les personvernerklæringen
                </a>
              </p>
            </div>
            <TrustSignals />
            <M1CoverageCard compact />
            <GenerationWizard />
          </motion.div>
        )}

        {/* State 2: Pipeline running */}
        {isGenerating && (
          <motion.div
            key="progress"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.25 }}
            className="pt-4"
          >
            <PipelineProgress />
          </motion.div>
        )}

        {/* State 3: Results */}
        {!isGenerating && result && (
          <motion.div
            key="result"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.25 }}
          >
            <ResultView />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
