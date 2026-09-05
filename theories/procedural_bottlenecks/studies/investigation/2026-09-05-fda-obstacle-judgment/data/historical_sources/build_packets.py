"""Build blind, source-only historical packets from retained primary-source captures."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import lxml.html
import pdfplumber

ROOT = Path(__file__).resolve().parent
AS_OF = "2026-05-15T12:00:00Z"
CAPTURED = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def html_blocks(path: Path) -> list[str]:
    raw = path.read_bytes()
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        decoded = raw.decode("cp1252", errors="replace")
    decoded = re.sub(r"<\?xml[^>]*\?>", "", decoded, flags=re.IGNORECASE)
    doc = lxml.html.fromstring(decoded)
    for bad in doc.xpath("//script|//style|//nav|//footer|//header|//noscript"):
        bad.drop_tree()
    blocks = []
    for node in doc.xpath("//h1|//h2|//h3|//h4|//p|//li|//td|//div"):
        if node.xpath("./p|./h1|./h2|./h3|./h4|./li|./td|./div"):
            continue
        text = clean(node.text_content())
        if (len(text) >= 35 and len(text.split()) <= 450
                and "us-gaap:" not in text and "Member20" not in text
                and "contextref=" not in text.lower()
                and "indicate by check mark" not in text.lower()
                and "file number assigned to the registrant" not in text.lower()):
            blocks.append(text)
    return list(dict.fromkeys(blocks))


def select_blocks(blocks: list[str], terms: list[str], max_words: int) -> str:
    priority = {"fda", "application", "nda", "pdufa", "priority review", "manufactur",
                "inspection", "resubmit", "resubmission", "complete response", "oai",
                "transfer", "cytisinicline", "gedatolisib", "commercial launch",
                "commercialization", "commercial readiness"}
    roots = []
    for i, block in enumerate(blocks):
        lower = block.lower()
        hits = {term for term in terms if term in lower}
        if hits:
            score = len(hits) + 5 * len(hits & priority)
            roots.append((score, i))
    indexes: set[int] = set()
    words = 0
    for _, i in sorted(roots, key=lambda item: (-item[0], item[1])):
        window = [j for j in range(max(0, i - 1), min(len(blocks), i + 2)) if j not in indexes]
        count = sum(len(blocks[j].split()) for j in window)
        if indexes and words + count > max_words:
            continue
        indexes.update(window)
        words += count
        if words >= max_words:
            break
    return "\n\n".join(blocks[i] for i in sorted(indexes))


def pdf_pages(path: Path, pages: list[int], max_words: int) -> str:
    chosen = []
    words = 0
    with pdfplumber.open(path) as pdf:
        for page_no in pages:
            text = clean(pdf.pages[page_no].extract_text() or "")
            count = len(text.split())
            if chosen and words + count > max_words:
                continue
            chosen.append(f"[PDF page {page_no + 1}] {text}")
            words += count
    return "\n\n".join(chosen)


BAX_PRIORITY_EXCERPT = """AstraZeneca’s New Drug Application (NDA) for baxdrostat has been accepted for Priority Review by the US Food and Drug Administration (FDA) in the US for the treatment of adult patients with hard-to-control (uncontrolled or treatment resistant) hypertension as an add-on to other antihypertensive medicines when these do not provide adequate lowering of blood pressure.

The Prescription Drug User Fee Act (PDUFA) date is anticipated during the second quarter of 2026 following use of a Priority Review voucher.

There are 1.4 billion people worldwide living with hypertension. In the US, approximately 50% of patients living with hypertension on multiple treatments do not have their blood pressure under control. Aldosterone is increasingly recognised as a key driver of hard-to-control hypertension, contributing to elevated cardiovascular and renal risk.

Sharon Barr, Executive Vice President, BioPharmaceuticals R&D, said: “This Priority Review demonstrates our commitment to advancing baxdrostat as a potential first- and best-in-class aldosterone synthase inhibitor for the millions of people living with hard-to-control hypertension as quickly as possible. The substantial reduction in systolic blood pressure seen in the BaxHTN trial underscores baxdrostat’s novel mechanism of action and its potential to bring innovation to a disease area that has seen limited progress in over two decades.”

The NDA is based on data from the BaxHTN Phase III trial which was presented during a Hot Line session at the European Society of Cardiology (ESC) Congress 2025 and simultaneously published in the New England Journal of Medicine. The trial showed that baxdrostat, on top of standard of care, met the primary and all secondary endpoints.

Standard of care consisted of a stable regimen of two antihypertensive agents at baseline, one of which is a diuretic (uncontrolled hypertension) or more than three antihypertensive agents at baseline, one of which is a diuretic (treatment-resistant hypertension). At week 12, the change from baseline and placebo-adjusted change from baseline reductions in mean seated SBP were 15.7 mmHg (95% confidence interval [CI], -17.6 to -13.7) and 9.8 mmHg (95% CI, -12.6 to -7.0; p<0.001) for the 2mg dose, and 14.5 mmHg (95% CI, -16.5 to -12.5) and 8.7 mmHg (95% CI, -11.5 to -5.8; p<0.001) for the 1mg dose, respectively. The results were consistent across both uncontrolled and treatment-resistant subgroups.

Baxdrostat was generally well tolerated with a safety profile consistent with its mechanism of action. There were no unanticipated safety findings, and most adverse events were mild.

The BaxHTN Phase III trial had three components to it that support the following endpoints: The primary endpoint was assessed during a 12-week double-blind, placebo-controlled period. A total of 796 patients were characterised in a 1:1:1 ratio to receive baxdrostat 2mg, 1mg or placebo once daily. The primary efficacy endpoint was the difference in mean change from baseline in seated SBP at week 12 between participants treated with baxdrostat (2mg or 1mg separately) and participants treated with placebo. Persistence of efficacy was assessed during a randomised withdrawal period from week 24 to week 32. Approximately 300 patients treated with baxdrostat 2mg were re-randomised in a 2:1 ratio to either continue receiving baxdrostat 2mg or placebo for the 8 weeks. SBP at the end of the 8 weeks was compared with placebo and the baxdrostat 2mg dose. Long-term safety is assessed at the end of the 52 weeks compared to a standard of care arm. Additional confirmatory secondary endpoints include the effect of baxdrostat versus placebo on seated SBP at week 12 in the resistant hypertension subpopulation, the effect of baxdrostat versus placebo on seated diastolic blood pressure at week 12, and proportion of participants achieving seated SBP less than 130 mmHg at week 12. Occurrence of adverse events was also evaluated."""


def source(case: str, source_id: str, title: str, url: str, published_at: str,
           raw_name: str, terms: list[str] | None = None, max_words: int = 900,
           availability_basis: str = "", manual_text: str | None = None,
           pdf_page_numbers: list[int] | None = None, locator: str = "") -> dict:
    path = ROOT / case / "raw" / raw_name
    if manual_text is not None:
        text = manual_text
    elif pdf_page_numbers is not None:
        text = pdf_pages(path, pdf_page_numbers, max_words)
    elif terms:
        text = select_blocks(html_blocks(path), terms, max_words)
    else:
        text = ""
    return {
        "source_id": source_id,
        "title": title,
        "url": url,
        "published_at": published_at,
        "captured_at": CAPTURED,
        "sha256": digest(path),
        "raw_path": path.relative_to(ROOT).as_posix(),
        "availability_basis": availability_basis,
        "text": text,
        "excerpt_locator": locator,
    }


REG = ["fda", "regulator", "application", "nda", "pdufa", "priority review", "trial", "endpoint", "safety", "adverse", "manufactur", "inspection", "resubmit", "complete response", "forward-looking", "commercial launch", "commercialization", "commercial readiness"]


def build() -> None:
    # Preserve the successful rendered-page excerpt separately from the CDN-denial response.
    bax_rendered = ROOT / "baxdrostat" / "raw" / "az_baxdrostat_nda_priority_review_2025-12-02.rendered_excerpt.txt"
    bax_rendered.write_text(BAX_PRIORITY_EXCERPT + "\n", encoding="utf-8")
    packets = {}
    packets["baxdrostat"] = {
        "subject_id": "baxdrostat", "as_of": AS_OF,
        "sources": [
            source("baxdrostat", "bax-release-nda-2025-12-02", "Baxdrostat New Drug Application accepted under FDA Priority Review in the US for patients with hard-to-control hypertension", "https://www.astrazeneca.com/media-centre/press-releases/2025/baxdrostat-new-drug-application-accepted-under-fda-priority-review-in-the-us-for-patients-with-hard-to-control-hypertension.html", "2025-12-02", "az_baxdrostat_nda_priority_review_2025-12-02.rendered_excerpt.txt", manual_text=BAX_PRIORITY_EXCERPT, availability_basis="Issuer page is dated 2 December 2025 and was readable on the official AstraZeneca site at capture. This retained text is a verbatim rendered-page excerpt, not the full response body; the separate .html file preserves the current CDN denial. Historical page-byte immutability is not established.", locator="Rendered issuer page: publication line and body from the NDA acceptance paragraph through BaxHTN trial notes."),
            source("baxdrostat", "bax-release-bax24-full-2025-11-09", "Bax24 Phase III trial full results", "https://www.astrazeneca.com/media-centre/press-releases/2025/bax24-phase-iii-trial-full-results.html", "2025-11-09", "az_bax24_full_results_2025-11-09.html", availability_basis="Official issuer URL and date were confirmed, but the raw retrieval returned AstraZeneca's CDN denial page and no complete historical copy was retained.", locator="No excerpt: failed raw retrieval retained."),
            source("baxdrostat", "bax-release-bax24-topline-2025-10-07", "Baxdrostat met the primary endpoint in Bax24 Phase III trial in patients with resistant hypertension", "https://www.astrazeneca.com/media-centre/press-releases/2025/baxdrostat-met-the-primary-endpoint-in-bax24-phase-iii-trial-in-patients-with-resistant-hypertension.html", "2025-10-07T14:30:06Z", "sec_bax24_topline_6k_2025-10-07.html", REG, 1300, "SEC-filed AstraZeneca Form 6-K accepted 2025-10-07 10:30:06 ET; immutable filing acceptance predates the cutoff.", locator="SEC Form 6-K body; keyword-matched paragraphs with adjacent qualifiers."),
        ],
        "coverage": {"categories": {"latest_pre_cutoff_10q_or_10k": "missing: AstraZeneca is a foreign private issuer and filed Form 20-F rather than 10-Q/10-K", "latest_three_predating_sponsor_releases": "three identified; two have usable verbatim excerpts and one failed raw retrieval", "latest_fda_application_document": "missing: no public application-specific FDA document found before cutoff"}, "missing": ["No qualifying Form 10-Q or 10-K.", "No public application-specific FDA document located before the cutoff.", "Complete raw body for the 2025-11-09 issuer release was not recoverable."], "limitations": ["AstraZeneca press pages are mutable; the current rendered NDA page does not prove byte-for-byte historical vintage.", "The retained 2025-11-09 curl capture is an explicit failed-retrieval artifact, not the release body."]}
    }

    packets["camizestrant"] = {
        "subject_id": "camizestrant", "as_of": AS_OF,
        "sources": [
            source("camizestrant", "cam-release-odac-2026-04-30", "Update on FDA Advisory Committee vote on camizestrant in combination with a CDK4/6 inhibitor for advanced HR-positive breast cancer", "https://www.astrazeneca.com/media-centre/press-releases/2026/fda-odac-vote-on-camizestrant-breast-cancer.html", "2026-04-30", "sec_cam_odac_6k_2026-05-01.html", REG, 650, "AstraZeneca release filed as Form 6-K and accepted by SEC on 2026-05-01 12:45:13 ET, before the cutoff.", locator="SEC Form 6-K body; relevant and adjacent paragraphs."),
            source("camizestrant", "cam-release-serena6-full-2025-06-01", "Camizestrant reduced the risk of disease progression or death by 56% in SERENA-6 Phase III trial", "https://www.astrazeneca.com/media-centre/press-releases/2025/camizestrant-reduced-the-risk-of-disease-progression-or-death-by-56-in-patients-with-advanced-hr-positive-breast-cancer-with-an-emergent-esr1-tumour-mutation-in-serena-6-phase-iii-trial.html", "2025-06-01", "az_camizestrant_serena6_full_2025-06-01.html", availability_basis="Official issuer URL and date confirmed; raw curl retrieval returned a CDN denial page.", locator="No excerpt: failed raw retrieval retained."),
            source("camizestrant", "cam-release-serena6-topline-2025-02-26", "Camizestrant demonstrated highly statistically significant and clinically meaningful improvement in progression-free survival in SERENA-6 Phase III trial", "https://www.astrazeneca.com/media-centre/press-releases/2025/camizestrant-improved-pfs-in-1l-hr-breast-cancer.html", "2025-02-26T16:08:27Z", "sec_cam_serena6_topline_6k_2025-02-26.html", REG, 600, "SEC-filed AstraZeneca Form 6-K accepted 2025-02-26 11:08:27 ET; immutable acceptance predates the cutoff.", locator="SEC Form 6-K body; relevant and adjacent paragraphs."),
            source("camizestrant", "cam-fda-briefing-2026-04-28", "Combined FDA and Applicant Briefing Document for the April 30, 2026 Oncologic Drugs Advisory Committee meeting", "https://www.fda.gov/media/192156/download", "2026-04-28", "fda_camizestrant_combined_briefing_2026-04-28.pdf", max_words=2700, availability_basis="FDA-hosted PDF cover states 'Initial Posting: April 28, 2026'; retained complete PDF and HTTP headers.", pdf_page_numbers=[0, 1, 14, 15, 16, 65, 66, 68], locator="PDF pp. 1-2, 15-17, 66-67, and 69: posting notice, disclaimer, regulatory history, FDA considerations, and voting question."),
        ],
        "coverage": {"categories": {"latest_pre_cutoff_10q_or_10k": "missing: AstraZeneca is a foreign private issuer and filed Form 20-F rather than 10-Q/10-K", "latest_three_predating_sponsor_releases": "three identified; two SEC-filed copies usable and one failed raw retrieval", "latest_fda_application_document": "covered by the FDA/applicant ODAC briefing document initially posted 2026-04-28"}, "missing": ["No qualifying Form 10-Q or 10-K.", "Complete raw body for the 2025-06-01 issuer release was not recoverable."], "limitations": ["The FDA briefing package expressly states that it may not include all issues relevant to final regulatory action.", "The retained 2025-06-01 curl capture is an explicit failed-retrieval artifact."]}
    }

    packets["cagrisema"] = {
        "subject_id": "cagrisema", "as_of": AS_OF,
        "sources": [
            source("cagrisema", "cag-release-eco-preview-2026-04-28", "Novo Nordisk to present new data across semaglutide portfolio and investigational treatments at ECO 2026", "https://www.novonordisk.com/news-and-media/news-and-ir-materials/news-details.html?id=916537", "2026-04-28T12:00:00Z", "novo_cagrisema_eco_preview_2026-04-28.html", REG + ["cagrisema", "redefine"], 650, "Official issuer URL, identifier, date, and search-rendered description were confirmed, but the retained direct response did not contain the release body.", locator="No excerpt: failed body retrieval retained."),
            source("cagrisema", "cag-release-redefine4-2026-02-23", "CagriSema demonstrates 23.0% weight loss in the REDEFINE 4 trial", "https://www.novonordisk.com/news-and-media/news-and-ir-materials/news-details.html?id=916501", "2026-02-23T09:33:18Z", "novo_cagrisema_redefine4_2026-02-23.html", REG + ["cagrisema", "redefine"], 1000, "Dated official Novo Nordisk issuer page captured complete; current mutable page.", locator="Issuer page trial and safety paragraphs with adjacent qualifiers."),
            source("cagrisema", "cag-release-reimagine2-2026-02-02", "CagriSema demonstrates superior reduction in HbA1c and body weight in REIMAGINE 2", "https://www.novonordisk.com/news-and-media/news-and-ir-materials/news-details.html?id=916481", "2026-02-02T15:43:01Z", "novo_cagrisema_reimagine2_2026-02-02.html", REG + ["cagrisema", "reimagine"], 1000, "Dated official Novo Nordisk issuer page captured complete; current mutable page.", locator="Issuer page trial and safety paragraphs with adjacent qualifiers."),
        ],
        "coverage": {"categories": {"latest_pre_cutoff_10q_or_10k": "missing: Novo Nordisk is a foreign private issuer and filed Form 20-F rather than 10-Q/10-K", "latest_three_predating_sponsor_releases": "three identified; two complete release bodies usable and the latest ECO preview body retrieval failed", "latest_fda_application_document": "missing: no public application-specific FDA document found before cutoff"}, "missing": ["No qualifying Form 10-Q or 10-K.", "No public application-specific FDA document located before cutoff.", "Complete raw body for the 2026-04-28 ECO preview release was not recoverable."], "limitations": ["Issuer news pages are current mutable captures; publication timestamps are issuer metadata, not independent archive timestamps.", "The retained 2026-04-28 response is an explicit failed-body artifact."]}
    }

    packets["cytisinicline"] = {
        "subject_id": "cytisinicline", "as_of": AS_OF,
        "sources": [
            source("cytisinicline", "cyt-sec-10q-2026q1", "Achieve Life Sciences Quarterly Report on Form 10-Q for quarter ended March 31, 2026", "https://www.sec.gov/Archives/edgar/data/949858/000119312526218177/achv-20260331.htm", "2026-05-12T11:21:43Z", "sec_2026q1_10q.html", REG + ["oai", "transfer", "resubmission", "cytisinicline"], 1400, "Immutable SEC filing accepted 2026-05-12 07:21:43 ET, before cutoff.", locator="Form 10-Q paragraphs concerning the NDA, OAI classification, manufacturing transfer, expected regulatory response, safety, and forward-looking risks."),
            source("cytisinicline", "cyt-release-q1-2026-05-12", "Achieve Life Sciences Reports First Quarter 2026 Financial Results and Provides Corporate Update", "https://ir.achievelifesciences.com/news-events/press-releases/detail/260/achieve-life-sciences-reports-first-quarter-2026", "2026-05-12T11:00:00Z", "achieve_cytisinicline_q1_update_2026-05-12.html", REG + ["oai", "cytisinicline"], 900, "Official issuer page states May 12, 2026 7:00 AM EDT; complete current HTML retained.", locator="Issuer release paragraphs concerning FDA review, OAI, expected regulatory response, manufacturing, trials, safety, and cautionary language."),
            source("cytisinicline", "cyt-release-manufacturing-2026-04-15", "Achieve Life Sciences Provides Update on Cytisinicline Manufacturing and Regulatory Process", "https://ir.achievelifesciences.com/news-events/press-releases/detail/256/achieve-life-sciences-provides-update-on-cytisinicline", "2026-04-15T12:00:00Z", "achieve_cytisinicline_manufacturing_2026-04-15.html", REG + ["oai", "cytisinicline"], 900, "Official issuer page states April 15, 2026 8:00 AM EDT; complete current HTML retained.", locator="Issuer release body and forward-looking qualifiers."),
            source("cytisinicline", "cyt-release-tolerability-2026-03-26", "Achieve Life Sciences Announces Publication of Cytisinicline Tolerability Data", "https://ir.achievelifesciences.com/news-events/press-releases/detail/255/achieve-life-sciences-announces-publication-of", "2026-03-26T12:30:00Z", "achieve_cytisinicline_tolerability_2026-03-26.html", REG + ["cytisinicline", "tolerability"], 650, "Official issuer page states March 26, 2026 8:30 AM EDT; complete current HTML retained.", locator="Issuer release tolerability and trial paragraphs with cautionary language."),
        ],
        "coverage": {"categories": {"latest_pre_cutoff_10q_or_10k": "covered by 2026 Q1 Form 10-Q", "latest_three_predating_sponsor_releases": "covered by the latest three substantive qualifying releases; a May 5 scheduling-only notice was excluded", "latest_fda_application_document": "missing: no public application-specific FDA document found before cutoff"}, "missing": ["No public application-specific FDA document located before cutoff."], "limitations": ["Issuer press pages are current mutable captures; SEC 10-Q supplies immutable pre-cutoff corroboration."]}
    }

    packets["gedatolisib"] = {
        "subject_id": "gedatolisib", "as_of": AS_OF,
        "sources": [
            source("gedatolisib", "ged-sec-10q-2026q1", "Celcuity Quarterly Report on Form 10-Q for quarter ended March 31, 2026", "https://www.sec.gov/Archives/edgar/data/1603454/000149315226023180/form10-q.htm", "2026-05-14T21:15:34Z", "sec_2026q1_10q.html", REG + ["gedatolisib", "viktoria"], 1400, "Immutable SEC filing accepted 2026-05-14 17:15:34 ET, before cutoff.", locator="Form 10-Q paragraphs concerning NDA review, VIKTORIA trials, safety, manufacturing/commercial readiness, and risks."),
            source("gedatolisib", "ged-release-viktoria2-2026-05-14", "Celcuity’s Phase 3 VIKTORIA-2 Trial of Gedatolisib as a First-Line Treatment Expanding to Include Endocrine-Sensitive Patients", "https://ir.celcuity.com/node/9646/pdf", "2026-05-14", "celcuity_viktoria2_2026-05-14.pdf", max_words=850, availability_basis="Complete issuer-hosted PDF downloaded through the rendered official page. The PDF is dated May 14, 2026; exact posting time and historical immutability are unavailable.", pdf_page_numbers=[0, 1, 2], locator="Complete three-page issuer PDF, capped after relevant body and forward-looking qualifiers."),
            source("gedatolisib", "ged-release-q1-2026-05-14", "Celcuity Reports First Quarter 2026 Financial Results and Provides Corporate Update", "https://www.sec.gov/Archives/edgar/data/1603454/000149315226023065/ex99-1.htm", "2026-05-14T20:05:21Z", "sec_2026-05-14_8k_ex99-1.html", REG + ["gedatolisib", "viktoria"], 900, "Press release retained as SEC Form 8-K Exhibit 99.1, accepted 2026-05-14 16:05:21 ET before cutoff.", locator="Exhibit 99.1 business highlights, regulatory, trial, readiness, safety, and cautionary paragraphs."),
            source("gedatolisib", "ged-release-viktoria1-2026-05-01", "Celcuity's Phase 3 VIKTORIA-1 Trial Achieves Primary Endpoint", "https://www.sec.gov/Archives/edgar/data/1603454/000149315226020918/ex99-1.htm", "2026-05-01T21:10:31Z", "sec_2026-05-01_8k_ex99-1.html", REG + ["gedatolisib", "viktoria"], 900, "Press release retained as SEC Form 8-K Exhibit 99.1, accepted 2026-05-01 17:10:31 ET before cutoff.", locator="Exhibit 99.1 efficacy, safety, intended sNDA, PDUFA, trial description, and cautionary paragraphs."),
        ],
        "coverage": {"categories": {"latest_pre_cutoff_10q_or_10k": "covered by 2026 Q1 Form 10-Q", "latest_three_predating_sponsor_releases": "covered by May 14 VIKTORIA-2, May 14 Q1 update, and May 1 VIKTORIA-1 releases", "latest_fda_application_document": "missing: no public application-specific FDA document found before cutoff"}, "missing": ["No public application-specific FDA document located before cutoff."], "limitations": ["The VIKTORIA-2 issuer PDF has a date but no independently archived exact posting time; the as-of cutoff is the following day at noon UTC."]}
    }

    for case, packet in packets.items():
        out = ROOT / case / "packet.json"
        out.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    manifest = []
    for path in sorted(ROOT.rglob("raw/*")):
        if path.is_file():
            manifest.append({"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)})
    (ROOT / "raw_manifest.json").write_text(json.dumps({"captured_at": CAPTURED, "files": manifest}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
