# Release evidence

> **Gjeldende release er `ff725bb69978`, deployet 6. august 2026.** Se
> «Kandidatrelease deployet» nederst. Avsnittene under gjelder den forrige
> releasen `69b00d81e5a7` og er historikk.

Status: `RELEASE CANDIDATE LOCAL / PRODUCTION GATE REJECTED`.

Backend-releasen er identitetsverifisert i Render, men den identiske
produksjonskjøringen oppfylte ikke kvalitetsporten og incidenten er derfor ikke
lukket. Render-dashboardet var ikke autentisert i denne kjøringen, så et
Render-deploy-ID kunne ikke hentes. Readiness-SHA og ikke-hemmelig
request-/Render-ID er likevel registrert nedenfor.

## Release scope

| Fil | Begrunnelse | Inkluderes? | Risiko |
|---|---|---:|---|
| `Skoleverksted/backend/platform/compendium.py` | Lærer-kilder, truth-kall, språkport og reparasjonsflyt | Ja | Ekte modell-/kildedata må verifiseres |
| `Skoleverksted/backend/platform/models.py` | Proveniens- og maskinstatusser | Ja | Gamle lagrede rader kan mangle nye felt |
| `Skoleverksted/backend/platform/router.py` | Timeout, lås, operation-ID og compile-gate | Ja | Daemon-worker kan leve etter timeout |
| `Skoleverksted/backend/platform/truth.py` | Kildekobling, status og setningssikker revisjon | Ja | Semantisk faktastøtte må testes med ekte kilder |
| `Skoleverksted/backend/platform/text_quality.py` | Deterministisk språkport | Ja | Heuristikk er ikke full grammatikkontroll |
| `Skoleverksted/backend/tests/test_compendium.py` | Tester for compendium-/reparasjonsregler | Ja | Produksjonsmiljø må fortsatt testes |
| `Skoleverksted/backend/tests/test_truth.py` | Tester for truth-status og kildeproveniens | Ja | URL-tilgjengelighet må verifiseres live |
| `Skoleverksted/backend/tests/test_text_quality.py` | Tester for strukturelle fragmenter | Ja | Kan ikke dekke alle modellvarianter |
| `Skoleverksted/backend/tests/test_history_fixtures.py` | Fem historiske regresjonsfixturer | Ja | Fixturetestene bruker ikke ekte modell |
| `MateMaTeX/frontend/src/app/compendia/[id]/page.tsx` | Synlige kapittel-/reparasjonsfeil | Ja | Må kontrolleres mot ny backend |
| `MateMaTeX/frontend/src/app/compendia/page.tsx` | Progress-/feilstatus for kompendier | Ja | Må kontrolleres i Vercel |
| `MateMaTeX/frontend/src/components/truth-passport.tsx` | Viser truth-status og kildeproveniens | Ja | UI må verifiseres E2E |
| `MateMaTeX/frontend/src/lib/platform-api.ts` | Timeout og retry for reparasjon | Ja | Nettverks-/refresh-scenario mangler |
| `render.yaml` | Eksplisitt reparasjonstimeout i production | Ja | Render må bekrefte faktisk sync |
| `evaluations/` | Anonymiserte identiske/regresjons-fixtures | Ja | Ikke produksjonsdata |
| `research/` og `status.md` | Audit-, gate- og releasebevis | Ja | Må oppdateres etter deploy |
| `VGS_KI/backend/test_akseptanse.py` | Pakkeimport som gjør full innsamling deterministisk | Ja | Ingen produktlogikk endres |
| `VGS_KI/backend/tests/test_main.py` | Pakkeimport for riktig `main`-modul | Ja | Ingen produktlogikk endres |
| `VGS_KI/backend/tests/test_job_manager.py` | Pakkeimport for riktig jobbmodul | Ja | Ingen produktlogikk endres |
| `VGS_KI/backend/tests/test_pdf_quality.py` | Pakkeimport for riktig renderer/pdf-service | Ja | Ingen produktlogikk endres |
| `MateMaTeX/backend/app/latex/preamble.py` | Urelatert LaTeX-justering | Nei | Bevisst utelatt |
| `MateMaTeX/backend/tests/test_hefte_design.py` | Urelatert LaTeX-test | Nei | Bevisst utelatt |

## Repository identity

| Felt | Verdi |
|---|---|
| Branch | `laerebokdesign-hefte` |
| Upstream | `origin/laerebokdesign-hefte` |
| Implementasjonscommit | `1c36544` (`Close compendium forensic incident and harden verification`) |
| Evidence-/releasecommit | `9d9ce24` (`Record forensic release evidence and deployment gate`) |
| Seneste produksjonscommit | `5b72a05` (`Fix nested heading quality gate`) |
| Dockerfile | `./Dockerfile` |
| Render Blueprint branch | `main` (må samsvare med deploystrategien) |
| Frontend | Vercel-prosjektet `skoleverksted` |

## Runtime-test

Eksisterende produksjonsnært image ble kjørt med arbeidskopien montert:

```text
docker run --rm -e GOOGLE_API_KEY=test-key -e PYTHONPATH=/app \
  -v C:\APP\VGS_samlet:/app -w /app vgs_samlet-backend:latest \
  python -m pytest -q
```

Resultat etter pakkeimportretting: **396 passed, 2 skipped, 47 warnings** in
53.26 s. Dette var før den siste porttesten. Seneste ferske image bestod med
**397 passed, 2 skipped, 47 warnings** på 45.51 s. Testen brukte ingen gyldig Google-nøkkel; en bakgrunnstest logget
forventet `API_KEY_INVALID`, men testprosessen bestod. Dette er ikke ekte
modell- eller produksjonsbevis.

Ferskt image (første forensic-release):

* Build-kommando: `docker buildx build --no-cache --pull --progress=plain --load -t skoleverksted-audit:20260803 .`
* Bygget: 2. august 2026 kl. 22:40 UTC (Docker metadata)
* Image-ID/digest: `sha256:fe99c5aafa50df4f58f543c8c04ba85ffb2243905d63787c39efd3f5ced70c40`
* Dockerfile-sjekker: Typst 0.14.2, pdfTeX/LuaHBTeX og `luaotfload-main.lua`

Ferskt image for seneste produksjonsrelease:

* Build-kommando: `docker buildx build --no-cache --pull --progress=plain --load -t skoleverksted-audit:20260803b .`
* Docker image digest: `sha256:034916e01d5787204e7b06d63832a0c299c98c5e857526fd31be511348eec646`
* Image metadata `Created`: `2026-08-02T23:11:51.192058533Z`
* Testresultat i image: **397 passed, 2 skipped, 47 warnings** på 45.51 s

Runtime-versjoner:

* Python 3.12.11
* FastAPI 0.141.1 (fresh image)
* Pydantic 2.12.5
* Pytest 8.4.2
* google-genai 1.65.0

## Deploybevis

| Felt | Verdi/status |
|---|---|
| Render deploy-ID | Ikke tilgjengelig fra uautentisert Render-dashboard. `rndr-id` for readiness-responsen: `7ce5fb96-3ba3-413f` (ikke deploy-ID) |
| Render verifisert SHA | `5b72a0541a20` fra `/health/ready` |
| Image-ID/digest | `sha256:034916e01d5787204e7b06d63832a0c299c98c5e857526fd31be511348eec646` lokalt bygget; Render image-digest er ikke eksponert av readiness |
| Deploy-/readiness-tidspunkt | Readiness-header `Date: Sun, 02 Aug 2026 23:31:51 GMT` |
| Readiness | HTTP 200; storage, Google AI, matematikk, norsk, Typst og pdfLaTeX `true`; `status=ready` |
| Promptversjon | `skoleverksted-v3` |
| Modell | `gemini-3.5-flash`; bilde: `gemini-3.1-flash-image` |
| Config fingerprint | `dc08f612a352` |
| Frontend-backend-kobling | `scripts/production_smoke.py` bestod på forsøk 1; Vercel `/`, `/fag`, `/norsk`, `/matematikk` og beskyttet matematikkproxy svarte 200 |
| Frontend-bevis | Vercel HTTP 200, `X-Vercel-Id: arn1::bl69g-1785713541664-6205d409a077`, `Date: Sun, 02 Aug 2026 23:32:22 GMT` |
| Rollback | Forrige verifiserte backend-SHA `9d9ce243620b`; Render-dashboardets deployreferanse mangler |

## Production scenario evidence

Den nye identiske produksjonskjøringen brukte kompendium-ID
`084614b8247d413b8d1ba38cb6166fce` og request-ID-er med prefiks
`audit-identical-20260803b-*`. Kapittelresponsene ble lagret lokalt uten
hemmeligheter. Resultatet var 14/14, 13/21 og 5/9 verifiserte påstander (32/44,
73 %), med kapittel 2 og 3 i `needs_revision`. Dette er ikke et grønt pass.

Repair-kallet for kapittel 2 fikk HTTP 504 etter den konfigurerte 120-sekunders
tidsgrensen med operation-ID `audit-identical-20260803b-repair-ch2`.
Umiddelbar retry ble kontrollert av kapittellåsen og svarte HTTP 409 med
`audit-identical-20260803b-repair-ch2` som aktiv jobb-ID. En vellykket ekte
modellreparasjon ble ikke observert i produksjon.

Kompilering av samme kompendium svarte HTTP 409 og listet alle tre kapitlene;
PDF/Word ble dermed korrekt blokkert.

Ingen hemmeligheter, tokens eller persondata er skrevet i dette dokumentet.

## Latest closure candidate — 3 August 2026

| Felt | Verdi/status |
|---|---|
| Candidate branch | `laerebokdesign-hefte` |
| Candidate commit | `2e66ec7a5467f3fc23523930ec9ac51181e7c070` |
| Candidate image | `skoleverksted-forensic:69b00d8-r1` |
| Candidate image digest | `sha256:db88579d5240abd7b1381ad0cfae035a7f8d73cbe01a11963ab92e685da47858` |
| Image Created | `2026-08-03T08:19:58.631325045Z` |
| Candidate backend tests | 398 passed, 2 skipped, 47 warnings, 28.96 s |
| Candidate frontend | 13 tests passed; typecheck and production build passed |
| Public readiness | HTTP 200, release `69b00d81e5a7`, `rndr-id=e947f2ef-2374-426d` |
| Candidate deploy status | Not deployed; current readiness SHA differs from candidate |
| Render deploy ID | Not available; `rndr-id` is not a dashboard deploy ID |
| Identical scenario on candidate | Not run because candidate is not deployed |
| Rollback reference | Historical deployed release `69b00d81e5a7`; forensic baseline `5b72a0541a20` |

The local candidate is intentionally not described as production-verified.

## Release candidate evidence — 3 August 2026, 16:54+02

| Felt | Verdi/status |
|---|---|
| Release candidate | `ff725bb6997879e74d60d1d539c57e18578f95ad` (`Document product excellence baseline`) |
| Code milestone | `912007bf5b4a68b736bbd14daa2011494bed266c` (`Make truth edits sentence-safe`) |
| Exact diff base | `origin/main..HEAD`: `2e66ec7`, `22b80d9`, `912007b`, `ff725bb`; 11 files, 809 additions, 29 deletions |
| Candidate image | `skoleverksted-candidate:ff725bb` |
| Candidate image digest | `sha256:d9fb7b5f4b4659aefdc729c34358b4e4d704716197f3ab96d3df7c32707c8792` |
| Candidate runtime suite | 398 passed, 2 skipped; Docker `compileall` passed |
| Frontend | 13 tests passed; TypeScript and production build passed |
| ESLint | `not operational`; root frontend has no ESLint config and `next lint` is interactive |
| Current Render release | `69b00d81e5a7d823eb284bc7aee37a8cac6f29ed`; readiness HTTP 200 |
| Current Render request ID | `rndr-id=e42efd6a-0b2f-4353`, `Date=Mon, 03 Aug 2026 14:53:12 GMT` |
| Render deploy ID | Not available; dashboard access is unauthenticated |
| Vercel production branch | Not proven from repository/public headers |
| Candidate deploy | Not performed; no compendium/job/artifact IDs created |
| Rollback | Redeploy Render SHA `69b00d81e5a7d823eb284bc7aee37a8cac6f29ed`; no force-push or data mutation |
| Manual product review | `pending teacher review` |
| Gate decision | `REJECTED` |

The current smoke passed once against the old release: readiness, frontend `/`
and `/compendia`, and the protected mathematics estimate returned HTTP 200.
This does not substitute for the missing candidate deploy, identical E2E,
successful repair, final PDF/Word artifacts, or teacher review.

---

## Kandidatrelease deployet — 6.–7. august 2026

Status: `DEPLOYED — PRODUCTION GATE REJECTED`.

### Releaseidentitet

| Felt | Verdi |
|---|---|
| Kandidatcommit | `ff725bb6997879e74d60d1d539c57e18578f95ad` |
| Kodecommit | `912007bf5b4a68b736bbd14daa2011494bed266c` |
| Kandidat-image (lokal verifikasjon) | `sha256:d9fb7b5f4b4659aefdc729c34358b4e4d704716197f3ab96d3df7c32707c8792` |
| Forrige release | `69b00d81e5a7d823eb284bc7aee37a8cac6f29ed` |
| Ny readiness-release | `ff725bb69978` |
| Config-fingerprint | `dc08f612a352` (uendret fra baseline) |

### Pushbevis

```
git push origin ff725bb6997879e74d60d1d539c57e18578f95ad:refs/heads/main
   69b00d8..ff725bb  ff725bb6997879e74d60d1d539c57e18578f95ad -> main
```

Fast-forward, ingen force, ingen merge-commit. Fire commits tilført:
`2e66ec7`, `22b80d9`, `912007b`, `ff725bb`. Lokale commits `266b1d2`,
`53fd943`, `3bb1970` og `72e3e3c` ble bevisst holdt utenfor releasen.

### Deploykjede

| Ledd | Bevis |
|---|---|
| GitHub `main` | `ff725bb6997879e74d60d1d539c57e18578f95ad` («Document product excellence baseline») |
| GitHub Actions | run `31104226437`, «Skoleverksted CI», conclusion `success`; jobbene `frontend`, `platform-backend`, `deterministic-domain-tests`, `full-domain-tests` alle `success` |
| Render-trigger | `autoDeployTrigger: checksPass` i `render.yaml` |
| Release-flipp observert | 2026-08-06 13:09:58Z |
| Readiness etter deploy | HTTP 200, `status=ready`, `rndr-id 965b3e3c-54f6-484f`, `X-Request-ID 6fb1632e23fd`, `Date Thu, 06 Aug 2026 13:10:16 GMT` |
| Produksjonssmoke | `scripts/production_smoke.py` bestod på forsøk 1 |
| Vercel | `/`, `/fag`, `/norsk`, `/matematikk` HTTP 200, region `arn1` |

### Fortsatt uten bevis

* Render-dashboardets deploy-ID, deploytidspunkt og deploystatus. Ingen
  `RENDER_API_KEY` tilgjengelig; releaseidentiteten er bevist via offentlig
  readiness-SHA og `rndr-id`-headere.
* Vercels konfigurerte production-branch og aktive deployment-ID. Ingen
  `VERCEL_TOKEN`; `vercel.json` inneholder ingen git-branch-konfigurasjon.
* Varig rå response-/reparasjonsledger i produksjon.
* Sluttartefakt: ingen PDF eller Word ble produsert
  (`artifact_version=0`, `pdf_size_bytes=0`, `docx_size_bytes=0`).

### Rollback

Rollbackmålet `69b00d81e5a7d823eb284bc7aee37a8cac6f29ed` er uendret og
tilgjengelig. Rollback utføres som redeploy av den commiten fra
Render-dashboardet. Force-push til `main` er ikke tillatt og ble ikke brukt.

### Korreksjon av tidligere testtall

Tidligere dokumentert «398 passed, 2 skipped» reproduserer ikke. Målt mot rene
worktrees i de eksakte imagene: baseline `69b00d8` gir **396 passed, 2
skipped**, kandidat `ff725bb` gir **402 passed, 2 skipped**. Differansen på +6
tilsvarer de seks nye testfunksjonene i `test_truth.py`.
