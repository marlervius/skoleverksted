"""Opt-in real-provider validation. Run only with explicit paid-API authorization."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

parser = argparse.ArgumentParser()
parser.add_argument('--allow-paid-api', action='store_true')
parser.add_argument('--run-id', required=True)
args = parser.parse_args()
if not args.allow_paid_api:
    raise SystemExit('Explicit paid API authorization required.')
if not args.run_id.isascii() or not all(c.isalnum() or c in '-_' for c in args.run_id):
    raise SystemExit('run-id must contain only ASCII letters, numbers, hyphens and underscores.')

out = ROOT / 'output' / 'source-recovery' / args.run_id
out.mkdir(parents=True, exist_ok=True)
from dotenv import dotenv_values
if not os.getenv('GOOGLE_API_KEY'):
    for env_path in (ROOT / 'ScriptoriumFOV/backend/.env', ROOT / 'MateMaTeX/.env'):
        values = dotenv_values(env_path)
        key = values.get('GOOGLE_API_KEY') or values.get('GEMINI_API_KEY')
        if key:
            os.environ['GOOGLE_API_KEY'] = key
            break
if not os.getenv('GOOGLE_API_KEY'):
    raise SystemExit('No configured Google API credential; no request sent.')
os.environ['APP_ENV'] = 'test'
os.environ['TEST_DATA_DIR'] = str(out / 'test-data')
os.environ['OUTPUT_DIR'] = str(out)
os.environ['CREWAI_DISABLE_TELEMETRY'] = 'true'
os.environ['OTEL_SDK_DISABLED'] = 'true'

from google import genai
from Skoleverksted.backend.platform.quality_gate import run_quality_pipeline, source_approval_reasons
from VGS_KI.backend.laeringsark_renderer import build_laeringsark_doc, coerce_structured_lesson
from VGS_KI.backend.pdf_service import compile_typst

# Bound this diagnostic independently of the application's normal retries.
real_client = genai.Client
calls = []
call_lock = threading.Lock()
class LimitedClient:
    def __init__(self, **kwargs):
        self.client = real_client(**kwargs)
        self.models = self
    def close(self):
        self.client.close()
    def generate_content(self, **kwargs):
        with call_lock:
            if len(calls) >= 8:
                raise RuntimeError('Diagnostic model-call budget exhausted')
            record = {'operation': 'research' if kwargs['config'].tools else 'assessment'}
            calls.append(record)
            call_number = len(calls)
        response = self.client.models.generate_content(**kwargs)
        usage = getattr(response, 'usage_metadata', None)
        record['usage'] = usage.model_dump(mode='json') if usage else {}
        observations = [getattr(candidate, 'grounding_metadata', None) for candidate in response.candidates or []]
        (out / f'model-response-{call_number}.json').write_text(json.dumps({
            'text': response.text,
            'grounding_metadata': [value.model_dump(mode='json') for value in observations if value],
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'model_call': call_number, **record}, ensure_ascii=True), flush=True)
        return response
genai.Client = LimitedClient

facts = [
    'Mesopotamia er et historisk område mellom elvene Eufrat og Tigris.',
    'Store deler av Mesopotamia ligger i dagens Irak.',
    'Sumer lå i den sørlige delen av Mesopotamia.',
    'Uruk var en viktig by i det gamle Mesopotamia.',
    'Sumererne brukte kileskrift.',
    'Kileskrift ble blant annet skrevet på leirtavler.',
    'Det gamle Egypt utviklet seg langs Nilen.',
    'Nilens oversvømmelser bidro til fruktbar jord.',
    'Faraoen var herskeren i det gamle Egypt.',
    'Egypterne brukte hieroglyfer som skriftsystem.',
    'Pyramidene i Giza ble bygd som graver for faraoer.',
    'Jordbruk gjorde det mulig å produsere mat til mennesker som hadde andre yrker.',
    'Byene i oldtiden hadde mennesker med ulike yrker og oppgaver.',
    'Handel knyttet samfunn i oldtiden sammen.',
    'Oldtidens samfunn hadde ulike sosiale grupper med ulik makt.',
]
structured = coerce_structured_lesson({
    'tittel': 'Oldtiden: Fra elvedaler til bysamfunn',
    'ingress': 'Undersøk hvordan elver, jordbruk og skrift fikk betydning for samfunnsutviklingen.',
    'seksjoner': [
        {'overskrift': 'Mesopotamia', 'avsnitt': facts[:6]},
        {'overskrift': 'Egypt', 'avsnitt': facts[6:11]},
        {'overskrift': 'Samfunn og arbeidsdeling', 'avsnitt': facts[11:]},
    ],
})
content = json.dumps({'canonical': structured, 'worksheet': 'Sammenlign elvenes betydning i Egypt og Mesopotamia. Drøft hvordan arbeidsdeling kan endre et samfunn.'}, ensure_ascii=False)
(out / 'input.json').write_text(content, encoding='utf-8')
result = run_quality_pipeline(
    generator_id='fag.learning_sheet', content=content, topic='Oldtiden', subject='Historie', level='VG2',
    progress_callback=lambda event: print(json.dumps(event, ensure_ascii=True), flush=True),
    request_id='live-source-recovery-' + args.run_id,
)
report = {
    'source_approved': result.source_approved, 'stop_reason': result.stop_reason,
    'passport': result.passport.model_dump(mode='json'),
    'rounds': [r.model_dump(mode='json') for r in result.rounds],
    'release_manifest': result.release_manifest.model_dump(mode='json'), 'calls': calls,
}
(out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
(out / 'approved-content.json').write_text(result.approved_content, encoding='utf-8')
if not result.source_approved:
    print(json.dumps({'result': 'blocked', 'stop_reason': result.stop_reason, 'report': str(out / 'report.json')}))
    raise SystemExit(2)
assert not source_approval_reasons(
    content=result.approved_content, verification_status=result.passport.status,
    verified_revision=result.passport.content_revision, verification_version=result.passport.version,
    release_manifest=report['release_manifest'],
)
verified = json.loads(result.approved_content)
document = build_laeringsark_doc(
    coerce_structured_lesson(verified['canonical']), fag='Historie', tema='Oldtiden', niva='VG2',
    modus='Teknisk kontrollutskrift', quality_verified=True,
)
pdf = compile_typst(document)
(out / 'oldtiden.pdf').write_bytes(pdf)
from pypdf import PdfReader
pages = PdfReader(out / 'oldtiden.pdf').pages
poppler = shutil.which('pdftoppm')
if poppler:
    subprocess.run([poppler, '-r', '90', '-png', str(out / 'oldtiden.pdf'), str(out / 'page')], check=True)
else:
    import fitz
    for i, page in enumerate(fitz.open(stream=pdf, filetype='pdf')):
        page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25)).save(out / f'page-{i+1}.png')
print(json.dumps({'result':'verified_pdf','claims':result.passport.verified_claims,'total':result.passport.total_claims,'pages':len(pages),'bytes':len(pdf),'document_hash':result.release_manifest.document_hash,'path':str(out / 'oldtiden.pdf')}))
