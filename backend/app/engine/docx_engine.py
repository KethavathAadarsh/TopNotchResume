"""
Dynamic DOCX Rendering Engine — Phase 3
Six format-specific visual themes, each with distinct typography, colors,
spacing, and structural layout. Themes are driven by the ResumeFormat enum.

Themes:
  ats       — Clean black & white, Calibri, 0.5" margins (ATS maximum compatibility)
  executive — Navy accent, Georgia, generous margins, title-case headers
  swe       — Dark teal accent, Calibri, code-friendly, GitHub-style project blocks
  startup   — Purple accent bar under name, Calibri, energetic density
  minimal   — Wide margins, generous whitespace, understated gray palette
  research  — Times New Roman, academic spacing, 1" margins
"""
import io
import logging
from dataclasses import dataclass, replace

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

logger = logging.getLogger(__name__)

PAGE_WIDTH_INCHES = 8.5


# ── Theme definitions ────────────────────────────────────────────────────────

@dataclass
class DocxTheme:
    name: str
    font_body: str
    font_header: str          # section headers
    color_name: RGBColor
    color_section: RGBColor
    color_body: RGBColor
    color_secondary: RGBColor  # company, italic lines
    border_color_hex: str     # section header bottom border
    font_size_body: int
    font_size_name: int
    font_size_section: int
    margin_inches: float
    section_caps: bool        # True → "EXPERIENCE", False → "Experience"
    accent_bar: bool          # colored thick bar below name header
    accent_bar_color_hex: str
    bullet_char: str
    space_section_before: float
    space_item_before: float


_THEMES: dict[str, DocxTheme] = {
    "ats": DocxTheme(
        name="ats",
        font_body="Calibri", font_header="Calibri",
        color_name=RGBColor(0, 0, 0),
        color_section=RGBColor(0, 0, 0),
        color_body=RGBColor(0, 0, 0),
        color_secondary=RGBColor(64, 64, 64),
        border_color_hex="000000",
        font_size_body=10, font_size_name=16, font_size_section=11,
        margin_inches=0.5, section_caps=True,
        accent_bar=False, accent_bar_color_hex="000000",
        bullet_char="•",
        space_section_before=7.0, space_item_before=4.0,
    ),
    "executive": DocxTheme(
        name="executive",
        font_body="Georgia", font_header="Georgia",
        color_name=RGBColor(27, 58, 107),    # deep navy
        color_section=RGBColor(27, 58, 107),
        color_body=RGBColor(30, 30, 30),
        color_secondary=RGBColor(80, 80, 80),
        border_color_hex="1B3A6B",
        font_size_body=10, font_size_name=18, font_size_section=11,
        margin_inches=0.75, section_caps=False,
        accent_bar=True, accent_bar_color_hex="1B3A6B",
        bullet_char="▸",
        space_section_before=9.0, space_item_before=5.0,
    ),
    "swe": DocxTheme(
        name="swe",
        font_body="Calibri", font_header="Calibri",
        color_name=RGBColor(15, 76, 117),    # dark teal
        color_section=RGBColor(15, 76, 117),
        color_body=RGBColor(20, 20, 20),
        color_secondary=RGBColor(70, 70, 70),
        border_color_hex="0F4C75",
        font_size_body=10, font_size_name=16, font_size_section=11,
        margin_inches=0.5, section_caps=True,
        accent_bar=False, accent_bar_color_hex="0F4C75",
        bullet_char="◆",
        space_section_before=7.0, space_item_before=4.0,
    ),
    "startup": DocxTheme(
        name="startup",
        font_body="Calibri", font_header="Calibri",
        color_name=RGBColor(79, 70, 229),    # vibrant indigo
        color_section=RGBColor(55, 48, 163),
        color_body=RGBColor(15, 15, 15),
        color_secondary=RGBColor(90, 90, 90),
        border_color_hex="4F46E5",
        font_size_body=10, font_size_name=17, font_size_section=10,
        margin_inches=0.5, section_caps=True,
        accent_bar=True, accent_bar_color_hex="4F46E5",
        bullet_char="→",
        space_section_before=6.0, space_item_before=3.5,
    ),
    "minimal": DocxTheme(
        name="minimal",
        font_body="Calibri", font_header="Calibri",
        color_name=RGBColor(30, 30, 30),
        color_section=RGBColor(120, 120, 120),
        color_body=RGBColor(50, 50, 50),
        color_secondary=RGBColor(130, 130, 130),
        border_color_hex="CCCCCC",
        font_size_body=10, font_size_name=15, font_size_section=10,
        margin_inches=0.85, section_caps=False,
        accent_bar=False, accent_bar_color_hex="CCCCCC",
        bullet_char="–",
        space_section_before=10.0, space_item_before=5.0,
    ),
    "research": DocxTheme(
        name="research",
        font_body="Times New Roman", font_header="Times New Roman",
        color_name=RGBColor(0, 0, 0),
        color_section=RGBColor(0, 0, 0),
        color_body=RGBColor(0, 0, 0),
        color_secondary=RGBColor(50, 50, 50),
        border_color_hex="000000",
        font_size_body=11, font_size_name=16, font_size_section=12,
        margin_inches=1.0, section_caps=False,
        accent_bar=False, accent_bar_color_hex="000000",
        bullet_char="•",
        space_section_before=10.0, space_item_before=5.0,
    ),
}

_DEFAULT_THEME = _THEMES["ats"]


def _get_theme(fmt: str) -> DocxTheme:
    return _THEMES.get(fmt, _DEFAULT_THEME)


# (layout key, min, max) — the range a composer override may set.
_LAYOUT_BOUNDS = (
    ("margin_inches", 0.4, 1.25),
    ("font_size_body", 9, 12),
    ("font_size_name", 14, 24),
)


def _clamp(value, lo: float, hi: float):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    clamped = max(lo, min(hi, value))
    return int(round(clamped)) if isinstance(lo, int) else float(clamped)


# ── Low-level XML helpers ────────────────────────────────────────────────────

def _set_bottom_border(paragraph, color_hex: str = "000000", sz: str = "6"):
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), sz)
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color_hex)
    p_bdr.append(bottom)
    p_pr.append(p_bdr)


def _add_right_tab(paragraph, position_inches: float):
    p_pr = paragraph._p.get_or_add_pPr()
    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "right")
    tab.set(qn("w:pos"), str(int(position_inches * 1440)))
    tabs.append(tab)
    p_pr.append(tabs)


def _set_para_spacing(paragraph, before: float = 0, after: float = 0, line_spacing: float = 1.0):
    pf = paragraph.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = Pt(line_spacing * 12)


def _make_run(paragraph, text: str, bold=False, italic=False,
              size: float = 10, color: RGBColor = RGBColor(0, 0, 0),
              font_name: str = "Calibri") -> None:
    run = paragraph.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(size)
    run.font.name = font_name
    run.font.color.rgb = color


def _add_thick_rule(doc: Document, color_hex: str):
    """Inserts a full-width colored horizontal rule (accent bar) as an XML border paragraph."""
    para = doc.add_paragraph()
    _set_para_spacing(para, before=0, after=4)
    p_pr = para._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "24")   # 3pt thick
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color_hex)
    p_bdr.append(bottom)
    p_pr.append(p_bdr)


# ── Document setup ───────────────────────────────────────────────────────────

def _setup_document(theme: DocxTheme) -> Document:
    doc = Document()

    for section in doc.sections:
        section.page_width = Inches(PAGE_WIDTH_INCHES)
        section.page_height = Inches(11)
        section.left_margin = Inches(theme.margin_inches)
        section.right_margin = Inches(theme.margin_inches)
        section.top_margin = Inches(theme.margin_inches)
        section.bottom_margin = Inches(theme.margin_inches)

    normal = doc.styles["Normal"]
    normal.font.name = theme.font_body
    normal.font.size = Pt(theme.font_size_body)
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(0)

    for section in doc.sections:
        section.different_first_page_header_footer = False
        section.header.is_linked_to_previous = True
        section.footer.is_linked_to_previous = True

    return doc


# ── Section renderers ────────────────────────────────────────────────────────

def _text_width(theme: DocxTheme) -> float:
    return PAGE_WIDTH_INCHES - 2 * theme.margin_inches


def _render_header(doc: Document, personal: dict, theme: DocxTheme):
    name = personal.get("name", "")
    display_name = name.upper() if theme.section_caps else name

    name_para = doc.add_paragraph()
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_para_spacing(name_para, before=0, after=2)
    _make_run(name_para, display_name, bold=True, size=theme.font_size_name,
              color=theme.color_name, font_name=theme.font_header)

    if theme.accent_bar:
        _add_thick_rule(doc, theme.accent_bar_color_hex)

    parts = [v for f in ("email", "phone", "location", "linkedin", "github", "website")
             if (v := personal.get(f, ""))]
    contact_para = doc.add_paragraph()
    contact_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_para_spacing(contact_para, before=0, after=6)
    _make_run(contact_para, "  |  ".join(parts), size=theme.font_size_body - 1,
              color=theme.color_secondary, font_name=theme.font_body)


def _render_section_header(doc: Document, raw_title: str, theme: DocxTheme):
    title = raw_title.upper() if theme.section_caps else raw_title.title()
    para = doc.add_paragraph()
    _set_para_spacing(para, before=theme.space_section_before, after=2)
    _make_run(para, title, bold=True, size=theme.font_size_section,
              color=theme.color_section, font_name=theme.font_header)
    _set_bottom_border(para, color_hex=theme.border_color_hex,
                       sz="4" if theme.name == "minimal" else "6")


def _render_summary(doc: Document, summary: str, theme: DocxTheme):
    if not summary:
        return
    _render_section_header(doc, "Professional Summary", theme)
    para = doc.add_paragraph()
    _set_para_spacing(para, before=0, after=2, line_spacing=1.15)
    _make_run(para, summary, size=theme.font_size_body,
              color=theme.color_body, font_name=theme.font_body)


def _render_bullet(doc: Document, text: str, theme: DocxTheme, indent: float = 0.2):
    para = doc.add_paragraph()
    para.paragraph_format.left_indent = Inches(indent)
    _set_para_spacing(para, before=0, after=1.5)
    _make_run(para, f"{theme.bullet_char}  {text}", size=theme.font_size_body,
              color=theme.color_body, font_name=theme.font_body)


def _render_experience(doc: Document, experience: list, theme: DocxTheme):
    if not experience:
        return
    _render_section_header(doc, "Experience", theme)
    tw = _text_width(theme)

    for item in experience:
        title_para = doc.add_paragraph()
        _set_para_spacing(title_para, before=theme.space_item_before, after=0)
        _add_right_tab(title_para, tw)
        _make_run(title_para, item.get("title", ""), bold=True,
                  size=theme.font_size_body + 1, color=theme.color_name,
                  font_name=theme.font_header)
        title_para.add_run("\t")
        date_text = f"{item.get('start_date', '')} – {item.get('end_date', 'Present')}"
        _make_run(title_para, date_text, size=theme.font_size_body - 1,
                  color=theme.color_secondary, font_name=theme.font_body)

        company_parts = [item.get("company", "")]
        if item.get("location"):
            company_parts.append(item["location"])
        company_para = doc.add_paragraph()
        _set_para_spacing(company_para, before=0, after=2)
        _make_run(company_para, ", ".join(company_parts), italic=True,
                  size=theme.font_size_body, color=theme.color_secondary,
                  font_name=theme.font_body)

        for bullet in item.get("bullets", []):
            _render_bullet(doc, bullet, theme)


def _render_skills(doc: Document, skill_sections: list, theme: DocxTheme):
    if not skill_sections:
        return
    _render_section_header(doc, "Skills", theme)

    for category in skill_sections:
        cat_name = category.get("category", "")
        items = category.get("items", [])
        if not items:
            continue
        para = doc.add_paragraph()
        _set_para_spacing(para, before=1, after=1)
        _make_run(para, f"{cat_name}:  ", bold=True, size=theme.font_size_body,
                  color=theme.color_section, font_name=theme.font_header)
        _make_run(para, ",  ".join(items), size=theme.font_size_body,
                  color=theme.color_body, font_name=theme.font_body)


def _render_projects(doc: Document, projects: list, theme: DocxTheme):
    if not projects:
        return
    _render_section_header(doc, "Projects", theme)

    for project in projects:
        proj_para = doc.add_paragraph()
        _set_para_spacing(proj_para, before=theme.space_item_before, after=0)
        _make_run(proj_para, project.get("name", ""), bold=True,
                  size=theme.font_size_body + 1, color=theme.color_name,
                  font_name=theme.font_header)
        techs = project.get("technologies", [])
        if techs:
            _make_run(proj_para, f"  |  {', '.join(techs)}", italic=True,
                      size=theme.font_size_body - 1, color=theme.color_secondary,
                      font_name=theme.font_body)
        url = project.get("url", "")
        if url:
            _make_run(proj_para, f"  —  {url}", size=theme.font_size_body - 1,
                      color=theme.color_secondary, font_name=theme.font_body)
        for bullet in project.get("bullets", []):
            _render_bullet(doc, bullet, theme)


def _render_education(doc: Document, education: list, theme: DocxTheme):
    if not education:
        return
    _render_section_header(doc, "Education", theme)
    tw = _text_width(theme)

    for entry in education:
        degree = entry.get("degree", "")
        if entry.get("field"):
            degree += f" in {entry['field']}"

        degree_para = doc.add_paragraph()
        _set_para_spacing(degree_para, before=theme.space_item_before, after=0)
        _add_right_tab(degree_para, tw)
        _make_run(degree_para, degree, bold=True, size=theme.font_size_body + 1,
                  color=theme.color_name, font_name=theme.font_header)
        degree_para.add_run("\t")
        _make_run(degree_para, entry.get("graduation_date", ""),
                  size=theme.font_size_body - 1, color=theme.color_secondary,
                  font_name=theme.font_body)

        inst_para = doc.add_paragraph()
        _set_para_spacing(inst_para, before=0, after=1)
        _make_run(inst_para, entry.get("institution", ""), italic=True,
                  size=theme.font_size_body, color=theme.color_secondary,
                  font_name=theme.font_body)

        extras = []
        if entry.get("gpa"):
            extras.append(f"GPA: {entry['gpa']}")
        if entry.get("honors"):
            extras.append(entry["honors"])
        if extras:
            ext_para = doc.add_paragraph()
            _set_para_spacing(ext_para, before=0, after=1)
            _make_run(ext_para, "  |  ".join(extras), size=theme.font_size_body - 1,
                      color=theme.color_secondary, font_name=theme.font_body)


def _render_certifications(doc: Document, certifications: list, theme: DocxTheme):
    if not certifications:
        return
    _render_section_header(doc, "Certifications", theme)

    for cert in certifications:
        parts = [cert.get("name", "")]
        if cert.get("issuer"):
            parts.append(cert["issuer"])
        cert_str = "  |  ".join(parts)
        if cert.get("date"):
            cert_str += f"  ({cert['date']})"
        _render_bullet(doc, cert_str, theme)


# ── Main render entry point ──────────────────────────────────────────────────

_SECTION_RENDERERS = {
    "summary": _render_summary,
    "experience": _render_experience,
    "skills": _render_skills,
    "projects": _render_projects,
    "education": _render_education,
    "certifications": _render_certifications,
}


def render_resume(composition: dict, resume_format: str = "ats") -> bytes:
    """
    Render a ResumeComposition dict to polished .docx bytes.
    `resume_format` selects the visual theme: ats | executive | swe | startup | minimal | research
    """
    # Layout overrides from the composer agent. Applied to a copy — the themes in
    # _THEMES are shared module state, so mutating them would leak one resume's
    # layout into every later render of that format. Values are clamped because
    # they come from the LLM.
    layout = composition.get("layout") or {}
    overrides = {}
    for key, lo, hi in _LAYOUT_BOUNDS:
        value = _clamp(layout.get(key), lo, hi)
        if value is not None:
            overrides[key] = value
    theme = replace(_get_theme(resume_format), **overrides)

    doc = _setup_document(theme)
    _render_header(doc, composition.get("personal", {}), theme)

    section_order = composition.get("section_order", [
        "summary", "experience", "skills", "projects", "education", "certifications"
    ])

    for section_key in section_order:
        renderer = _SECTION_RENDERERS.get(section_key)
        if renderer is None:
            continue
        if section_key == "summary":
            renderer(doc, composition.get("summary", ""), theme)
        elif section_key == "experience":
            renderer(doc, composition.get("experience", []), theme)
        elif section_key == "skills":
            renderer(doc, composition.get("skill_sections", []), theme)
        elif section_key == "projects":
            renderer(doc, composition.get("projects", []), theme)
        elif section_key == "education":
            renderer(doc, composition.get("education", []), theme)
        elif section_key == "certifications":
            renderer(doc, composition.get("certifications", []), theme)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    logger.info("DOCX rendered: format=%s theme=%s", resume_format, theme.name)
    return buffer.read()
