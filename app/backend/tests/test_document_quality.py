"""Stage 7 (spec K): synthetic documents through the real pandoc conversion + template."""

import re
import types
from pathlib import Path

import pytest
from docx import Document

from app.config import settings
from app.deliverables import _PLACEHOLDER_RE, _document_check, _pandoc_convert, strip_comments

FIX = Path(__file__).parent / "fixtures" / "documents"
TEMPLATE = Path(settings.TEMPLATES_DIR) / "resume_template.docx"

CANDIDATES = {
    "experienced": dict(
        name="MAXIMILIANO ALEJANDRO FERNÁNDEZ-OYELARAN", word_cap=900,
        contact={"location": "Austin, TX", "email": "max.fernandez@example.test",
                 "phone": "(512) 555-0147", "linkedin": "linkedin.com/in/example-maximiliano"},
    ),
    "early_career": dict(
        name="TESSA OKONKWO-BELL", word_cap=600,
        contact={"location": "Houston, TX", "email": "tessa.okonkwo@example.test",
                 "linkedin": "linkedin.com/in/example-tessa"},
    ),
}
DOCX_DOCS = ["resume", "targeted_resume", "cover_letter", "interview_prep", "score_card"]
GENERIC_PLACEHOLDER = re.compile(r"\[[^\]\n]{1,60}\]|\bTBD\b|\bTODO\b|lorem ipsum|\bX{2,}\b|<!--", re.I)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


def _text(level: str, doc: str) -> str:
    ext = "html" if doc == "skills_matrix" else "md"
    return (FIX / level / f"{doc}.{ext}").read_text(encoding="utf-8")


def _convert(tmp_path, level, doc) -> Path:
    src = tmp_path / f"{level}_{doc}.md"
    src.write_text(_text(level, doc), encoding="utf-8")
    out = tmp_path / f"{level}_{doc}.docx"
    _pandoc_convert(src, out, TEMPLATE)
    return out


def _plain(s: str) -> str:
    return " ".join(s.replace("**", "").replace("’", "'").split())


def test_template_present():
    assert TEMPLATE.is_file()


@pytest.mark.parametrize("doc", DOCX_DOCS)
@pytest.mark.parametrize("level", list(CANDIDATES))
def test_docx_text_headings_and_placeholders(tmp_path, level, doc):
    cfg = CANDIDATES[level]
    md = _text(level, doc)
    docx_path = _convert(tmp_path, level, doc)
    d = Document(docx_path)
    paras = [p for p in d.paragraphs if p.text.strip()]
    texts = [_plain(p.text) for p in paras]
    # selectable text: the candidate's name is real paragraph text, not an image
    first_line = _plain(md.splitlines()[0].lstrip("# ").strip())
    assert any(first_line in t for t in texts), first_line
    # every markdown heading is a Word heading paragraph with a matching level
    expected = []
    for ln in md.splitlines():
        m = HEADING_RE.match(ln)
        if m:
            expected.append((len(m.group(1)), _plain(m.group(2))))
    assert expected or doc == "cover_letter"
    by_text = {_plain(p.text): p for p in paras}
    for level_n, title in expected:
        p = by_text.get(title)
        assert p is not None, f"heading not found in DOCX: {title!r}"
        assert p.style.name.startswith("Heading"), (title, p.style.name)
        assert p.style.name == f"Heading {level_n}", (title, p.style.name)
    # body text came through (a sample of bullet/list lines)
    body = [_plain(re.sub(r"^\s*[-*>]\s+", "", ln)) for ln in md.splitlines()
            if re.match(r"^\s*[-*]\s+\S", ln)]
    all_text = " ".join(texts)
    for b in body[:6]:
        assert b in all_text, b
    # no placeholders
    assert not _PLACEHOLDER_RE.search(all_text)
    assert not GENERIC_PLACEHOLDER.search(md), GENERIC_PLACEHOLDER.search(md)
    assert not GENERIC_PLACEHOLDER.search(all_text)
    # tables (score card) still carry real text
    if doc == "score_card":
        assert d.tables and any("Clarity" in c.text for t in d.tables for r in t.rows for c in r.cells)


@pytest.mark.parametrize("level", list(CANDIDATES))
def test_resume_length_proxy(tmp_path, level):
    cfg = CANDIDATES[level]
    for doc in ("resume", "targeted_resume"):
        d = Document(_convert(tmp_path, level, doc))
        words = sum(len(p.text.split()) for p in d.paragraphs)
        assert 150 < words <= cfg["word_cap"], (level, doc, words)


@pytest.mark.parametrize("doc", DOCX_DOCS + ["skills_matrix"])
@pytest.mark.parametrize("level", list(CANDIDATES))
def test_fixtures_pass_the_real_generation_check(level, doc):
    """The same contact/placeholder check generation applies accepts the fixture documents."""
    session = types.SimpleNamespace(discovery_data={"contact": CANDIDATES[level]["contact"]})
    check = _document_check(session)
    assert check(_text(level, doc)) is None
    # and rejects an unconfirmed email appended to it
    assert check(_text(level, doc) + "\nother.person@elsewhere.test\n") == "email"


@pytest.mark.parametrize("hidden,kind", [
    ("<other.person@elsewhere.test>", "email"),
    ('<a href="mailto:other.person@elsewhere.test">Email me</a>', "email"),
    ('<a href="mailto:other.person%40elsewhere.test">Email me</a>', "email"),
    ("other.person&#64;elsewhere.test", "email"),
    ('<a href="tel:+15125550199">Call</a>', "phone"),
])
def test_check_sees_contact_details_inside_links(hidden, kind):
    """Autolinks and mailto:/tel: targets render as contact links, so the check must see them."""
    session = types.SimpleNamespace(discovery_data={"contact": CANDIDATES["experienced"]["contact"]})
    check = _document_check(session)
    base = _text("experienced", "resume")
    assert check(base) is None
    assert check(base + "\n" + hidden + "\n") == kind


@pytest.mark.parametrize("level", list(CANDIDATES))
def test_skills_matrix_html_is_inert_and_complete(level):
    html = _text(level, "skills_matrix")
    assert "<script" not in html.lower() and "javascript:" not in html.lower()
    assert not GENERIC_PLACEHOLDER.search(strip_comments(html))
    assert html.count("<table") == html.count("</table>") >= 1
    assert re.search(r"<h2>[^<]+</h2>", html)


def test_long_name_is_not_truncated_in_docx(tmp_path):
    d = Document(_convert(tmp_path, "experienced", "resume"))
    head = d.paragraphs[0].text
    assert "FERNÁNDEZ-OYELARAN" in head and "MAXIMILIANO ALEJANDRO" in head
