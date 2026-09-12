"""Regenerate a truncated draft in complete, bounded pieces; never reuse it."""

import re
import time

from app.models.state import PipelineState
from app.pipeline.cancel import is_cancelled
from Skoleverksted.backend.platform.quality_runtime import run_bounded_sync


def generate_in_parts(llm, system: str, prompt: str, state: PipelineState) -> str:
    request = state.request
    parts = ["Dokumentets innledning, læringsmål og den bestilte teorien. Ingen oppgaver eller løsningsforslag."]
    if request.include_examples or request.include_graphs:
        parts.append("De bestilte gjennomregnede eksemplene og figurene. Ingen ny innledning eller oppgavesamling.")
    if request.include_exercises:
        for first in range(1, request.num_exercises + 1, 5):
            last = min(first + 4, request.num_exercises)
            solution_instruction = (
                "Ta med fullstendige løsningsforslag for akkurat disse oppgavene."
                if request.include_solutions else "Ikke ta med løsningsforslag."
            )
            parts.append(f"Bare oppgave {first} til {last}, med disse oppgavenumrene. {solution_instruction}")
    complete_parts = []
    deadline = time.monotonic() + 300
    for index, instruction in enumerate(parts, 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0 or is_cancelled(state.job_id):
            raise RuntimeError("Oppdelt generering nådde tidsgrensen eller ble avbrutt")
        part_prompt = (
            f"{prompt}\n\nOPPDELT GENERERING – DEL {index} AV {len(parts)}:\n"
            f"{instruction}\n"
            "Skriv kun denne delen, maksimalt 1800 ord, som komplett LaTeX-body uten preamble. "
            "Lukk alle miljøer og formler. Ikke gjenta tidligere deler. Bevar kravene til "
            "materialtype, emne og nivå. Ikke utelat noen av oppgavene i denne delen.\n"
            "TIDLIGERE FERDIGE DELER (kun kontekst):\n" + "\n\n".join(complete_parts)
        )
        response = run_bounded_sync(
            lambda part_prompt=part_prompt: llm.invoke(system, part_prompt),
            timeout_seconds=remaining,
            cancel_check=lambda: is_cancelled(state.job_id),
            operation_name=f"partitioned author {index}/{len(parts)}",
        )
        response = re.sub(r"^```(?:latex|tex)?\s*", "", response.strip())
        response = re.sub(r"\s*```$", "", response)
        if not response.strip() or re.search(r"\\(?:documentclass|begin\{document\}|end\{document\})", response):
            raise ValueError("En generert del er tom eller inneholder en dokumentramme")
        complete_parts.append(response)
    # The normal math, content, source and PDF gates still check the assembly.
    return "\n\n".join(complete_parts)
