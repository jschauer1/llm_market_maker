"""Capture and excerpt the fixed-cutoff primary-source packets for the FDA study.

This script is deliberately local to the study data folder.  It records full
response bytes and headers before producing bounded, verbatim excerpts.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[6]
PRIOR = REPO / "theories/procedural_bottlenecks/studies/answer/2026-09-05-procedural-viability/data/fda"
AS_OF = "2026-09-05T18:30:00Z"
UA = "Market Edge Finder academic research source archive contact jbs00@example.invalid"


def S(subject, sid, category, title, url, published, aliases, *, reuse=None, note="", force=False):
    return dict(subject=subject, source_id=sid, category=category, title=title,
                url=url, published_at=published.removesuffix("T00:00:00Z"), aliases=aliases, reuse=reuse, note=note, force=force)


SOURCES = [
    S("cagrisema", "cag_novo_20260607_reimagine", "sponsor_release", "Novo Nordisk's CagriSema 2.4 mg / 2.4 mg demonstrated significant reduction in HbA1c and weight across multiple studies in the REIMAGINE program presented at ADA 2026", "https://www.novonordisk.com/news-and-media/news-and-ir-materials/news-details.html?id=916567", "2026-06-07T21:31:24Z", ["cagrisema", "reimagine"]),
    S("cagrisema", "cag_novo_20260527_ada_preview", "sponsor_release", "Novo Nordisk advances cardiometabolic pipeline with new data featuring CagriSema and zenagamtide at the American Diabetes Association's 2026 Scientific Sessions", "https://www.novonordisk.com/news-and-media/news-and-ir-materials/news-details.html?id=916555", "2026-05-27T13:00:00Z", ["cagrisema", "reimagine"]),
    S("cagrisema", "cag_novo_20260428_eco_preview", "sponsor_release", "Novo Nordisk to present new data on Wegovy, women with obesity and next-generation weight loss treatments at European Congress on Obesity", "https://www.globenewswire.com/news-release/2026/04/28/3282534/0/en/Novo-Nordisk-to-present-new-data-on-Wegovy-women-with-obesity-and-next-generation-weight-loss-treatments-at-European-Congress-on-Obesity.html", "2026-04-28T12:00:00Z", ["cagrisema", "redefine"], note="Full issuer-authored release captured from Novo Nordisk's distribution service, GlobeNewswire.", force=True),
    S("cagrisema", "cag_novo_20251218_nda_submission", "application_context", "Novo Nordisk files for FDA approval of CagriSema, the first once-weekly combination of GLP-1 and amylin analogues for weight management", "https://www.novonordisk.com/news-and-media/news-and-ir-materials/news-details.html?id=916470", "2025-12-18T12:00:00Z", ["cagrisema", "fda", "application"], reuse="cag_submission.html"),

    S("cytisinicline", "cyt_sec_2026q2_10q", "sec_filing", "Achieve Life Sciences, Inc. Quarterly Report on Form 10-Q for the quarter ended June 30, 2026", "https://www.sec.gov/Archives/edgar/data/949858/000119312526344624/achv-20260630.htm", "2026-08-11T00:00:00Z", ["cytisinicline"]),
    S("cytisinicline", "cyt_achieve_20260811_q2", "sponsor_release", "Achieve Life Sciences Reports Second Quarter 2026 Financial Results and Provides Business Updates", "https://ir.achievelifesciences.com/news-events/press-releases/detail/268/achieve-life-sciences-reports-second-quarter-2026-financial-results-and-provides-business-updates", "2026-08-11T00:00:00Z", ["cytisinicline", "complete response", "fda"]),
    S("cytisinicline", "cyt_achieve_20260622_crl", "sponsor_release", "Achieve Life Sciences Receives Complete Response Letter from FDA for Cytisinicline NDA", "https://ir.achievelifesciences.com/news-events/press-releases/detail/264/achieve-life-sciences-receives-complete-response-letter-from-fda-for-cytisinicline-nda", "2026-06-22T00:00:00Z", ["cytisinicline", "complete response", "fda"]),
    S("cytisinicline", "cyt_achieve_20260512_q1", "sponsor_release", "Achieve Life Sciences Reports First Quarter 2026 Financial Results and Provides Business Updates", "https://ir.achievelifesciences.com/news-events/press-releases/detail/260/achieve-life-sciences-reports-first-quarter-2026-financial-results-and-provides-business-updates", "2026-05-12T00:00:00Z", ["cytisinicline", "nda", "fda"]),
    S("cytisinicline", "cyt_fda_20260620_crl_nda218995", "fda_application_document", "Complete Response Letter, NDA 218995 (cytisinicline)", "https://download.open.fda.gov/crl/CRL_NDA218995_20260620_Redacted.pdf", "2026-06-20T00:00:00Z", ["cytisinicline", "inspection", "manufactur", "label", "safety"]),

    S("midomafetamine_mdma_for_ptsd", "mdma_lykos_20250116_fda_meeting", "sponsor_release", "Lykos Therapeutics Statement on Latest FDA Meeting", "https://news.lykospbc.com/2025-01-16-Lykos-Therapeutics-Statement-on-Latest-FDA-Meeting", "2025-01-16T00:00:00Z", ["fda", "midomafetamine", "mdma", "resubmission"]),
    S("midomafetamine_mdma_for_ptsd", "mdma_lykos_20241018_fda_meeting", "sponsor_release", "Lykos Therapeutics Statement on Recent FDA Meeting", "https://news.lykospbc.com/2024-10-18-Lykos-Therapeutics-Statement-on-Recent-FDA-Meeting", "2024-10-18T00:00:00Z", ["fda", "midomafetamine", "mdma", "resubmission"]),
    S("midomafetamine_mdma_for_ptsd", "mdma_lykos_20240905_leadership", "sponsor_release", "Lykos Therapeutics Announces Appointments of Michael Mullette as Interim Chief Executive Officer and Dr. David Hough as Chief Medical Officer", "https://news.lykospbc.com/2024-09-05-Lykos-Therapeutics-Announces-Appointments-of-Michael-Mullette-as-Interim-Chief-Executive-Officer-and-Dr-David-Hough-as-Chief-Medical-Officer", "2024-09-05T00:00:00Z", ["fda", "midomafetamine", "mdma", "complete response"]),
    S("midomafetamine_mdma_for_ptsd", "mdma_fda_20240808_crl_nda215455", "fda_application_document", "Complete Response Letter, NDA 215455 (midomafetamine capsules)", "https://download.open.fda.gov/crl/CRL_NDA215455_20240808.pdf", "2024-08-08T00:00:00Z", ["midomafetamine", "inspection", "clinical", "safety", "label"], reuse="mdma_crl.pdf"),

    S("comp360_psilocybin", "cmps_sec_2026q2_10q", "sec_filing", "COMPASS Pathways plc Quarterly Report on Form 10-Q for the quarter ended June 30, 2026", "https://www.sec.gov/Archives/edgar/data/1816590/000181659026000058/cmps-20260630.htm", "2026-08-05T00:00:00Z", ["comp360", "psilocybin"]),
    S("comp360_psilocybin", "cmps_20260805_q2", "sponsor_release", "Compass Pathways Announces Second Quarter and First Half 2026 Financial Results and Business Highlights", "https://ir.compasspathways.com/News--Events-/news/news-details/2026/Compass-Pathways-Announces-Second-Quarter-and-First-Half-2026-Financial-Results-and-Business-Highlights/default.aspx", "2026-08-05T00:00:00Z", ["comp360", "psilocybin", "fda", "rolling"]),
    S("comp360_psilocybin", "cmps_20260707_comp006_6month", "sponsor_release", "Compass Pathways Announces Six-Month Data from Second Phase 3 Trial Confirming Rapid and Durable Profile", "https://ir.compasspathways.com/News--Events-/news/news-details/2026/Compass-Pathways-Announces-Six-Month-Data-from-Second-Phase-3-Trial-Confirming-Rapid-and-Durable-Profile/default.aspx", "2026-07-07T00:00:00Z", ["comp360", "comp 006", "fda", "safety"]),
    S("comp360_psilocybin", "cmps_20260513_q1", "sponsor_release", "Compass Pathways Announces First Quarter 2026 Financial Results and Business Highlights", "https://ir.compasspathways.com/News--Events-/news/news-details/2026/Compass-Pathways-Announces-First-Quarter-2026-Financial-Results-and-Business-Highlights/default.aspx", "2026-05-13T00:00:00Z", ["comp360", "psilocybin", "fda", "submission"]),
    S("comp360_psilocybin", "cmps_20260424_rolling_cnpv", "pathway_exception", "Compass Pathways Announces FDA Granted NDA Rolling Review Request and Awarded Commissioner's National Priority Voucher", "https://ir.compasspathways.com/News--Events-/news/news-details/2026/Compass-Pathways-Announces-FDA-Granted-NDA-Rolling-Review-Request-and-Awarded-Commissioners-National-Priority-Voucher/", "2026-04-24T00:00:00Z", ["rolling review", "voucher", "fda", "comp360"]),
    S("comp360_psilocybin", "cmps_fda_20260424_cnpv_release", "fda_pathway_document", "FDA Accelerates Action on Treatments for Serious Mental Illness Following Executive Order", "https://www.fda.gov/news-events/press-announcements/fda-accelerates-action-treatments-serious-mental-illness-following-executive-order", "2026-04-24T00:00:00Z", ["psilocybin", "voucher", "priority", "depression"]),

    S("retatrutide", "reta_sec_2026q2_10q", "sec_filing", "Eli Lilly and Company Quarterly Report on Form 10-Q for the quarter ended June 30, 2026", "https://www.sec.gov/Archives/edgar/data/59478/000005947826000081/lly-20260630.htm", "2026-08-05T00:00:00Z", ["retatrutide", "triumph"]),
    S("retatrutide", "reta_lilly_20260805_q2", "sponsor_release", "Lilly reports second-quarter 2026 financial results, raises full-year guidance, and highlights continued growth and pipeline progress", "https://www.prnewswire.com/news-releases/lilly-reports-second-quarter-2026-financial-results-raises-full-year-guidance-and-highlights-continued-growth-and-pipeline-progress-302843165.html", "2026-08-05T10:45:00Z", ["retatrutide", "triumph", "submission"], note="Full issuer-authored release captured from Lilly's distribution service, PR Newswire."),
    S("retatrutide", "reta_lilly_20260723_phase3", "sponsor_release", "Lilly's triple agonist, retatrutide, successful in two additional Phase 3 obesity trials, delivering significant improvements in weight and A1C", "https://www.prnewswire.com/news-releases/lillys-triple-agonist-retatrutide-successful-in-two-additional-phase-3-obesity-trials-delivering-significant-improvements-in-weight-and-a1c-302832674.html", "2026-07-23T10:45:00Z", ["retatrutide", "fda", "submit", "safety"], note="Full issuer-authored release captured from Lilly's distribution service, PR Newswire."),
    S("retatrutide", "reta_lilly_20260606_phase3", "sponsor_release", "Lilly's triple agonist retatrutide drove substantial improvements in weight, A1C, knee osteoarthritis pain and obstructive sleep apnea across four Phase 3 trials", "https://www.prnewswire.com/news-releases/lillys-triple-agonist-retatrutide-drove-substantial-improvements-in-weight-a1c-knee-osteoarthritis-pain-and-obstructive-sleep-apnea-demonstrating-its-remarkable-potential-to-treat-obesity-and-its-complications-302793169.html", "2026-06-06T18:30:00Z", ["retatrutide", "triumph", "safety"], note="Full issuer-authored release captured from Lilly's distribution service, PR Newswire."),

    S("v940_intismeran_autogene", "v940_moderna_sec_2026q2_10q", "sec_filing", "Moderna, Inc. Quarterly Report on Form 10-Q for the quarter ended June 30, 2026", "https://www.sec.gov/Archives/edgar/data/1682852/000168285226000150/mrna-20260630.htm", "2026-07-31T00:00:00Z", ["intismeran", "v940", "mrna-4157"]),
    S("v940_intismeran_autogene", "v940_merck_sec_2026q2_10q", "sec_filing", "Merck & Co., Inc. Quarterly Report on Form 10-Q for the quarter ended June 30, 2026", "https://www.sec.gov/Archives/edgar/data/310158/000031015826000212/mrk-20260630.htm", "2026-08-07T00:00:00Z", ["intismeran", "v940", "mrna-4157"]),
    S("v940_intismeran_autogene", "v940_merck_moderna_20260819_phase3", "sponsor_release", "Merck and Moderna Announce Phase 3 INTerpath-001 Trial of Intismeran Autogene Plus KEYTRUDA Met Endpoints of Recurrence-Free Survival and Distant Metastasis-Free Survival", "https://www.merck.com/news/merck-and-moderna-announce-phase-3-interpath-001-trial-of-intismeran-autogene-plus-keytruda-met-endpoints-of-recurrence-free-survival-rfs-and-distant-metastasis-free-survival-dmfs-in-patient/", "2026-08-19T00:00:00Z", ["intismeran", "v940", "regulator", "safety"]),
    S("v940_intismeran_autogene", "v940_merck_20260804_q2", "sponsor_release", "Merck Announces Second-Quarter 2026 Financial Results; Highlights Key Regulatory and Clinical Milestones Across Broad, Diverse Pipeline", "https://www.merck.com/news/merck-highlights-key-regulatory-and-clinical-milestones-across-broad-diverse-pipeline/", "2026-08-04T00:00:00Z", ["intismeran", "v940", "fda", "regulatory"]),
    S("v940_intismeran_autogene", "v940_merck_moderna_20260601_5year", "sponsor_release", "Moderna and Merck Present 5-Year Data for Intismeran Autogene in Combination with KEYTRUDA in Patients with High-Risk Stage III/IV Melanoma Following Complete Resection", "https://www.merck.com/news/moderna-and-merck-present-5-year-data-for-intismeran-autogene-in-combination-with-keytruda-pembrolizumab-in-patients-with-high-risk-stage-iii-iv-melanoma-following-complete-resection-at-the-20/", "2026-06-01T00:00:00Z", ["intismeran", "v940", "safety", "phase 2"]),

    S("lonvoguran_ziclumeran_lonvo_z", "lonvo_sec_2026q2_10q", "sec_filing", "Intellia Therapeutics, Inc. Quarterly Report on Form 10-Q for the quarter ended June 30, 2026", "https://www.sec.gov/Archives/edgar/data/1652130/000119312526337952/ntla-20260630.htm", "2026-08-06T00:00:00Z", ["lonvoguran", "lonvo-z", "ntla-2002"]),
    S("lonvoguran_ziclumeran_lonvo_z", "lonvo_intellia_20260806_q2", "sponsor_release", "Intellia Therapeutics Announces Second Quarter 2026 Financial Results and Business Updates", "https://www.globenewswire.com/news-release/2026/08/06/3340073/0/en/intellia-therapeutics-announces-second-quarter-2026-financial-results-and-business-updates.html", "2026-08-06T11:00:00Z", ["lonvoguran", "lonvo-z", "bla", "fda"], note="Full issuer-authored release captured from Intellia's distribution service, GlobeNewswire."),
    S("lonvoguran_ziclumeran_lonvo_z", "lonvo_intellia_20260613_phase3", "sponsor_release", "Intellia Therapeutics Reports Additional Positive Phase 3 Results for Lonvoguran Ziclumeran (lonvo-z) in Patients with Hereditary Angioedema", "https://www.globenewswire.com/news-release/2026/06/13/3311378/0/en/Intellia-Therapeutics-Reports-Additional-Positive-Phase-3-Results-for-Lonvoguran-Ziclumeran-lonvo-z-in-Patients-with-Hereditary-Angioedema.html", "2026-06-13T11:30:00Z", ["lonvoguran", "lonvo-z", "safety", "bla"], note="Full issuer-authored release captured from Intellia's distribution service, GlobeNewswire."),
    S("lonvoguran_ziclumeran_lonvo_z", "lonvo_intellia_20260601_eaaci", "sponsor_release", "Intellia Therapeutics to Report Additional Phase 3 HAELO Data for Lonvoguran Ziclumeran (lonvo-z) in Late-Breaking Oral Presentation at EAACI 2026", "https://www.globenewswire.com/news-release/2026/6/1/3304241/0/en/intellia-therapeutics-to-report-additional-phase-3-haelo-data-for-lonvoguran-ziclumeran-lonvo-z-in-late-breaking-oral-presentation-at-eaaci-2026.html", "2026-06-01T11:30:00Z", ["lonvoguran", "lonvo-z", "phase 3", "safety"], note="Full issuer-authored release captured from Intellia's distribution service, GlobeNewswire."),
    S("lonvoguran_ziclumeran_lonvo_z", "lonvo_intellia_20260427_rolling_bla", "pathway_exception", "Intellia Therapeutics Initiates Rolling Submission of Biologics License Application to FDA for Lonvoguran Ziclumeran (lonvo-z) as a One-Time Treatment for Hereditary Angioedema", "https://ir.intelliatx.com/node/12611/pdf", "2026-04-27T00:00:00Z", ["lonvoguran", "rolling", "bla", "fda"], reuse="ntla_rolling_bla_apr2026.pdf"),
    S("lonvoguran_ziclumeran_lonvo_z", "lonvo_fda_cdrp_program", "fda_pathway_document", "Chemistry, Manufacturing, and Controls Development and Readiness Pilot (CDRP) Program", "https://www.fda.gov/drugs/pharmaceutical-quality-resources/chemistry-manufacturing-and-controls-development-and-readiness-pilot-cdrp-program", "2026-07-23T00:00:00Z", ["manufactur", "readiness", "rolling", "application"]),
    S("lonvoguran_ziclumeran_lonvo_z", "lonvo_fda_rmat_program", "fda_pathway_document", "Regenerative Medicine Advanced Therapy Designation", "https://www.fda.gov/vaccines-blood-biologics/cellular-gene-therapy-products/regenerative-medicine-advanced-therapy-designation", "2026-06-05T00:00:00Z", ["rmat", "designation", "breakthrough", "intensive guidance"], note="Page publication metadata may be earlier; date records latest FDA page update visible before cutoff."),
]


SUBJECT_NOTES = {
    "cagrisema": {"missing": ["No SEC Form 10-Q/10-K: Novo Nordisk is a foreign private issuer that reports on Forms 20-F and 6-K.", "No public FDA application-specific document was located for the pending NDA."], "limitations": ["The December 2025 submission release is included as application context in addition to the three latest qualifying sponsor releases.", "Same-subject source exposure exists in the prior study; this packet is not an untouched holdout input."]},
    "cytisinicline": {"missing": [], "limitations": ["The FDA Commissioner's National Priority Voucher awarded for vaping cessation concerns a different proposed indication than the smoking-cessation NDA and is not treated as a pathway exception for NDA 218995.", "Same-subject source exposure exists in the prior study; this packet is not an untouched holdout input."]},
    "midomafetamine_mdma_for_ptsd": {"missing": ["No SEC Form 10-Q/10-K: Lykos Therapeutics is privately held."], "limitations": ["The selected sponsor releases are the three latest located before the cutoff whose body concerns FDA review or response work; the FDA CRL supplies application-specific detail."]},
    "comp360_psilocybin": {"missing": ["No public FDA application-specific review document was located for the pending rolling NDA submission."], "limitations": ["The dated April 24, 2026 FDA release corroborates the voucher category but does not name COMPASS; sponsor attribution is preserved separately."]},
    "retatrutide": {"missing": ["No public FDA application-specific document: the sponsor stated it planned an FDA submission in the first quarter of 2027, after this packet's cutoff."], "limitations": []},
    "v940_intismeran_autogene": {"missing": ["No public FDA application-specific document was located; the sponsors had reported Phase 3 results and planned regulatory engagement, without a public submission acceptance by the cutoff."], "limitations": ["Both joint sponsors' latest Forms 10-Q are retained."]},
    "lonvoguran_ziclumeran_lonvo_z": {"missing": ["No public FDA application-specific review document was located for the pending rolling BLA."], "limitations": ["FDA CDRP and RMAT pages describe the pathways generally; sponsor materials establish the subject-specific designations.", "FDA program pages are mutable; their captured bytes and visible update metadata are retained, and they are used only for pathway mechanics known by the cutoff."]},
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def clean(s):
    return re.sub(r"\s+", " ", s).strip()


def html_blocks(data, wide=False):
    soup = BeautifulSoup(data, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav"]):
        tag.decompose()
    blocks = []
    tags = ["h1", "h2", "h3", "p", "li", "tr"] if not wide else ["h1", "h2", "h3", "p", "li", "div", "span", "td"]
    for tag in soup.find_all(tags):
        t = clean(tag.get_text(" ", strip=True))
        if len(t) >= 35 and (not wide or len(t.split()) <= 350) and t not in blocks:
            blocks.append(t)
    return blocks


def pdf_blocks(path):
    blocks = []
    reader = PdfReader(str(path))
    for page_no, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        for para in re.split(r"\n\s*\n|(?<=\.)\s*\n", text):
            t = clean(para)
            if len(t) >= 35:
                blocks.append(f"[PDF page {page_no}] {t}")
    return blocks


REG = ["fda", "application", "submission", "review", "approval", "complete response", "trial", "phase 3", "phase iii", "endpoint", "safety", "adverse", "manufactur", "inspection", "label", "resubmit", "rolling", "priority", "voucher", "rmat", "cdrp", "regulator", "bla", "nda"]

CYT_CRL_PAGE1 = """[PDF page 1; visually transcribed because the page has no embedded text] NDA 218995. COMPLETE RESPONSE.

Please refer to your new drug application (NDA) dated and received June 20, 2025, and your amendments, submitted under [redacted] for cytisinicline tablet, [redacted].

We have completed our review of this application, as amended, and have determined that we cannot approve this application in its present form. We have described our reasons for this action below and, where possible, our recommendations to address these issues.

FACILITY INSPECTIONS

(1) Following a CGMP inspection of [redacted], listed in this application, FDA conveyed deficiencies to the representative of the facility. The facility should provide satisfactory responses to these deficiencies to the FDA office indicated on FDA Form 483 prior to your Complete Response submission. The facility's satisfactory responses are dependent on FDA's determination that the facility has come into compliance with CGMP and may require re-inspection of the facility. The deficiencies identified during the inspection may not be specific to your application. Therefore, you should coordinate with the facility for timely resolution. Your complete response should include the date(s) of the facility's response(s) to the FDA Form 483. Please refer to Compliance Program CP 7356.002 for guidance on post inspection activities. Following resolution of the CGMP inspection, FDA may need to conduct a prior approval inspection (PAI) of the facility.

PRESCRIBING INFORMATION

(2) Submit draft labeling that is responsive to our electronic communication dated June 4, 2026, as part of your resubmission."""

MDMA_CRL_PAGE1 = """[PDF page 1; visually transcribed because the page has no embedded text] NDA 215455. COMPLETE RESPONSE.

Please refer to your new drug application [redacted] for midomafetamine capsules.

We also acknowledge receipt of your amendment dated [redacted], which was not reviewed for this action. You may incorporate applicable sections of the amendment by specific reference as part of your response to the deficiencies cited in this letter.

We have completed our review of this application, as amended, and have determined that we cannot approve this application in its present form. We have described our reasons for this action below and, where possible, our recommendations to address these issues.

COMPLETE RESPONSE ISSUES

We have concluded that your application does not provide substantial evidence of effectiveness or establish the safety of your product to support the approval of midomafetamine for the treatment of posttraumatic stress disorder (PTSD). We have identified several issues with the application that preclude its approval.

1. You did not collect important information on events that the participant, therapist, or study physician considered "positive" or "favorable." This information is necessary for FDA to assess signals of abuse potential and patient impairment in the clinical trials in order to adequately describe the drug effects in labeling and inform appropriate monitoring for the safe use of midomafetamine. In addition, FDA inspections also identified several unreported adverse events for at least two sites, which increase our concerns about the reliability of the safety data.

FDA had advised in our [redacted] communication that "For all Phase 1, 2 and 3 studies, AEs associated with potential abuse or overdose must be documented," and we referred you to our guidance for industry, Assessment of Abuse Potential of Drugs (2017) for recommendations regarding how to appropriately document adverse events associated with abuse potential even if they are considered desirable (e.g., euphoria-related experiences, mood changes)."""

CURATED_HTML_PHRASES = {
    "lonvo_sec_2026q2_10q": [
        "We significantly advanced our launch readiness activities in recent months",
        "Our business may be adversely affected if we are unable to successfully file and obtain approval",
    ],
}


def curated_excerpt(source_id, blocks):
    if source_id == "cmps_sec_2026q2_10q":
        tests = [
            lambda b: b.startswith("Following these data read-outs") and "National Priority Voucher for COMP360 psilocybin treatment in TRD." in b,
            lambda b: b.startswith("We have in the past published") and "preliminary results from our Phase 3 trials" in b,
            lambda b: b.startswith("With a rolling review, the FDA may consider") and b.endswith("regulatory approval."),
            lambda b: b.startswith("We have received a National Priority Review voucher for COMP360"),
            lambda b: b.startswith("In June 2025, the FDA announced") and len(b.split()) > 150,
            lambda b: b.startswith("appropriate by the FDA. The National Priority Review program"),
        ]
        chosen = []
        for test in tests:
            matches = [(i, b) for i, b in enumerate(blocks) if test(b)]
            if matches:
                i, b = min(matches, key=lambda pair: len(pair[1].split()))
                if b.startswith("We have in the past published"):
                    b = b.replace(" Material adverse changes in the final data compared to the interim data could significantly harm our business prospects or cause the price of our stock to decline.", "")
                if b not in {x[1] for x in chosen}: chosen.append((i, b))
        chosen.sort()
        return "\n\n".join(b for _, b in chosen), "HTML extracted blocks " + ",".join(str(i + 1) for i, _ in chosen) + "; source-specific regulatory and qualification selection"
    if source_id in CURATED_HTML_PHRASES:
        chosen = []
        for phrase in CURATED_HTML_PHRASES[source_id]:
            matches = [(i, b) for i, b in enumerate(blocks) if phrase.lower() in b.lower()]
            if matches:
                i, b = min(matches, key=lambda pair: len(pair[1].split()))
                if b not in {x[1] for x in chosen}: chosen.append((i, b))
        chosen.sort()
        return "\n\n".join(b for _, b in chosen), "HTML extracted blocks " + ",".join(str(i + 1) for i, _ in chosen) + "; source-specific regulatory selection"
    if source_id == "cyt_fda_20260620_crl_nda218995":
        indexes = list(range(0, 21)) + [23, 24, 25]
        return CYT_CRL_PAGE1 + "\n\n" + "\n\n".join(blocks[i] for i in indexes), "PDF page 1 visually verified and transcribed; embedded text from pages 2-5"
    if source_id == "mdma_fda_20240808_crl_nda215455":
        indexes = list(range(0, 12))
        return MDMA_CRL_PAGE1 + "\n\n" + "\n\n".join(blocks[i] for i in indexes), "PDF page 1 visually verified and transcribed; complete-response clinical issue text from pages 2-5"
    return None


def excerpt(blocks, aliases, category, source_id, target=650):
    curated = curated_excerpt(source_id, blocks)
    if curated is not None:
        return curated
    keys = [x.lower() for x in aliases]
    candidates = {}
    boilerplate = ("worldwide see our worldwide", "the .gov means it", "email the url of this page", "accept cookies", "privacy policy", "skip to main")
    for i, block in enumerate(blocks):
        low = block.lower()
        alias = any(k in low for k in keys)
        relevant = any(k in low for k in REG)
        if alias and (relevant or category != "sec_filing"):
            score = 20 + 4 * sum(k in low for k in keys) + 2 * sum(k in low for k in REG)
            candidates[i] = max(candidates.get(i, 0), score)
            if category != "sec_filing":
                for j in range(max(0, i - 1), min(len(blocks), i + 2)):
                    near = blocks[j].lower()
                    if j != i and any(k in near for k in REG) and not any(x in near for x in boilerplate) and len(blocks[j].split()) >= 8:
                        candidates[j] = max(candidates.get(j, 0), 2 + sum(k in near for k in REG))
    if not candidates:
        for i, block in enumerate(blocks):
            if any(k in block.lower() for k in keys):
                candidates[i] = 10
    out, words = [], 0
    chosen = []
    for i, _score in sorted(candidates.items(), key=lambda item: (-item[1], len(blocks[item[0]].split()), item[0])):
        b = blocks[i]
        n = len(b.split())
        if n > target or (words and words + n > target):
            continue
        chosen.append(i); words += n
        if words >= target - 25:
            break
    out = [(i, blocks[i]) for i in sorted(chosen)]
    if words < min(180, target) and category != "sec_filing":
        for i, b in enumerate(blocks):
            if i in chosen or len(b.split()) < 8 or any(x in b.lower() for x in boilerplate):
                continue
            n = len(b.split())
            if words + n > target:
                continue
            out.append((i, b)); words += n
            if words >= min(350, target):
                break
        out.sort()
    loc = "HTML extracted blocks " + ",".join(str(i + 1) for i, _ in out)
    if any(b.startswith("[PDF page") for _, b in out):
        pages = sorted({re.search(r"page (\d+)", b).group(1) for _, b in out if b.startswith("[PDF page")})
        loc = "PDF pages " + ",".join(pages)
    return "\n\n".join(b for _, b in out), loc


def main():
    raw_dir = ROOT / "raw"; head_dir = ROOT / "headers"; packet_dir = ROOT / "packets"
    for d in (raw_dir, head_dir, packet_dir): d.mkdir(parents=True, exist_ok=True)
    receipts, successful = [], []
    session = requests.Session(); session.headers.update({"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
    for spec in SOURCES:
        ext = ".pdf" if spec["url"].lower().endswith(".pdf") or (spec.get("reuse") or "").endswith(".pdf") else ".html"
        raw_path = raw_dir / f'{spec["source_id"]}{ext}'
        head_path = head_dir / f'{spec["source_id"]}.headers.json'
        attempted = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        receipt = {"source_id": spec["source_id"], "url": spec["url"], "attempted_at": attempted}
        try:
            if raw_path.exists() and raw_path.stat().st_size and not spec.get("force"):
                headers = json.loads(head_path.read_text(encoding="utf-8")) if head_path.exists() else {"note": "raw response already present"}
                status = "existing_capture"
            elif spec.get("reuse"):
                src = PRIOR / spec["reuse"]
                if not src.exists(): raise FileNotFoundError(src)
                shutil.copyfile(src, raw_path)
                headers_src = PRIOR / f'{Path(spec["reuse"]).stem}_headers.txt'
                headers = {"reused_from": str(src.relative_to(REPO)).replace("\\", "/")}
                if headers_src.exists(): headers["original_headers"] = headers_src.read_text(encoding="utf-8", errors="replace")
                status = "reused_original"
            else:
                response = session.get(spec["url"], timeout=20, allow_redirects=True)
                response.raise_for_status()
                raw_path.write_bytes(response.content)
                headers = {"status_code": response.status_code, "final_url": response.url, "headers": dict(response.headers)}
                status = "captured_http"
            head_path.write_text(json.dumps(headers, indent=2, ensure_ascii=False), encoding="utf-8")
            data = raw_path.read_bytes()
            captured = datetime.fromtimestamp(raw_path.stat().st_ctime, timezone.utc).isoformat().replace("+00:00", "Z")
            blocks = pdf_blocks(raw_path) if ext == ".pdf" else html_blocks(data, spec["category"] == "sec_filing")
            text, locator = excerpt(blocks, spec["aliases"], spec["category"], spec["source_id"])
            record = {**spec, "raw_path_obj": raw_path, "captured_at": captured, "sha256": sha(data), "text": text, "excerpt_locator": locator, "status": status}
            successful.append(record)
            receipt.update({"status": status, "raw_path": str(raw_path.relative_to(ROOT)).replace("\\", "/"), "bytes": len(data), "sha256": record["sha256"], "extracted_blocks": len(blocks), "excerpt_words": len(text.split())})
        except Exception as exc:
            receipt.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}"})
        receipts.append(receipt)
        (ROOT / "retrieval_receipts.json").write_text(json.dumps(receipts, indent=2, ensure_ascii=False), encoding="utf-8")

    subjects = sorted({x["subject"] for x in SOURCES})
    summary = {}
    for subject in subjects:
        wanted = [x for x in SOURCES if x["subject"] == subject]
        got = [x for x in successful if x["subject"] == subject]
        categories = {}
        for x in got: categories.setdefault(x["category"], []).append(x["source_id"])
        failures = [x["source_id"] for x in wanted if x["source_id"] not in {g["source_id"] for g in got}]
        notes = SUBJECT_NOTES[subject]
        packet = {
            "subject_id": subject,
            "as_of": AS_OF,
            "sources": [{
                "source_id": x["source_id"], "title": x["title"], "url": x["url"],
                "published_at": x["published_at"], "captured_at": x["captured_at"], "sha256": x["sha256"],
                "raw_path": str(x["raw_path_obj"].relative_to(ROOT)).replace("\\", "/"),
                "availability_basis": ("Original response bytes reused without modification from the prior study archive; source publication predates the fixed cutoff." if x["status"] == "reused_original" else "Primary-source response captured after the fixed cutoff; the source carries a publication or filing date that predates the cutoff.") + ((" " + x["note"]) if x.get("note") else ""),
                "text": x["text"], "excerpt_locator": x["excerpt_locator"],
            } for x in got],
            "coverage": {
                "categories": categories,
                "missing": notes["missing"] + (["Capture failed for planned source IDs: " + ", ".join(failures)] if failures else []),
                "limitations": notes["limitations"] + ["This is a current-cohort source packet; it makes no untouched-input holdout claim.", "Excerpts are verbatim text selected from retained full raw bytes; navigation and unrelated financial boilerplate are omitted."]
            }
        }
        path = packet_dir / f"{subject}.json"
        path.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
        summary[subject] = {"packet": str(path.relative_to(ROOT)).replace("\\", "/"), "sources": len(got), "planned": len(wanted), "excerpt_words": sum(len(x["text"].split()) for x in got), "failures": failures}
    (ROOT / "collection_summary.json").write_text(json.dumps({"as_of": AS_OF, "subjects": summary}, indent=2), encoding="utf-8")
    query_receipt = {
        "as_of": AS_OF,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "selection_rule": "For each subject, retain the latest SEC Form 10-Q/10-K when one exists, the three latest qualifying sponsor releases before the cutoff, the latest public FDA application-specific document when one exists, and dated pathway documents needed to describe a subject-specific exception.",
        "archive_queries": [
            {"url": "https://investor.lilly.com/rss/news-releases.xml", "terms": ["retatrutide", "FDA", "Phase 3", "submission"], "selected_source_ids": ["reta_lilly_20260805_q2", "reta_lilly_20260723_phase3", "reta_lilly_20260606_phase3"]},
            {"url": "https://ir.intelliatx.com/rss/news-releases.xml", "terms": ["lonvoguran", "lonvo-z", "BLA", "FDA", "Phase 3"], "selected_source_ids": ["lonvo_intellia_20260806_q2", "lonvo_intellia_20260613_phase3", "lonvo_intellia_20260601_eaaci"]},
            {"query": "site:prnewswire.com/news-releases Lilly retatrutide July 23 2026 triple agonist successful two additional phase 3", "selected_source_ids": ["reta_lilly_20260723_phase3"]},
            {"query": "site:prnewswire.com/news-releases Lilly retatrutide June 6 2026 substantial improvements", "selected_source_ids": ["reta_lilly_20260606_phase3"]},
            {"query": "site:globenewswire.com Intellia Lonvoguran June 13 2026 HAELO", "selected_source_ids": ["lonvo_intellia_20260613_phase3"]},
            {"query": "site:globenewswire.com Intellia Second Quarter 2026 Financial Results Lonvoguran", "selected_source_ids": ["lonvo_intellia_20260806_q2"]},
            {"query": "\"Intellia Therapeutics to Report Additional Phase 3 HAELO Data\" GlobeNewswire", "selected_source_ids": ["lonvo_intellia_20260601_eaaci"]},
            {"query": "\"Novo Nordisk to present new data on Wegovy\" \"April 28, 2026\"", "selected_source_ids": ["cag_novo_20260428_eco_preview"]},
        ],
        "source_index": [{"source_id": x["source_id"], "category": x["category"], "title": x["title"], "url": x["url"], "published_at": x["published_at"]} for x in SOURCES],
        "limitations": ["Exact timestamps for browser search execution were not exposed; all searches and captures occurred after the fixed source cutoff.", "Publication eligibility comes from source-carried dates, filing dates, and retained originals, not retrieval time.", "HTTP response-level success and failure details are in retrieval_receipts.json."],
    }
    (ROOT / "query_receipts.json").write_text(json.dumps(query_receipt, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
