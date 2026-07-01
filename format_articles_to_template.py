import html
import re
import subprocess
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "formatted_articles"
LOGO_PATH = (BASE_DIR / "web" / "assets" / "dp.png").resolve()

ARTICLES = [
    {
        "source": Path("/home/gala/Downloads/Раздел_1_1,_Динамическое_научное_издание_нового_типа.docx"),
        "slug": "section_1_1_dynamic_scientific_edition",
        "chapter_number": "1",
        "chapter_title": "Об издании DNS и проекте Клуб-DP",
        "section_number": "1.1",
        "title": "Динамическое научное издание нового типа",
    },
    {
        "source": Path("/home/gala/Downloads/Раздел_1_2_Как_теория_информации_изменила_науку.docx"),
        "slug": "section_1_2_information_theory",
        "chapter_number": "1",
        "chapter_title": "Об издании DNS и проекте Клуб-DP",
        "section_number": "1.2",
        "title": "Как теория информации изменила науку",
    },
    {
        "source": Path("/home/gala/Downloads/Раздел_2_0_Как_математика_сделала_из_обезьяны_чнловека.docx"),
        "slug": "section_2_0_mathematics_and_human",
        "chapter_number": "2",
        "chapter_title": "Цифровизация естественно-научных дисциплин",
        "section_number": "2.0",
        "title": "Как математика сделала из обезьяны человека",
    },
    {
        "source": Path("/home/gala/Downloads/Раздел 2.1. Метаязык.pdf"),
        "slug": "section_2_1_metalanguage",
        "chapter_number": "2",
        "chapter_title": "Цифровизация естественно-научных дисциплин",
        "section_number": "2.1",
        "title": "Метаязык",
    },
]


def extract_docx_paragraphs(path: Path) -> list[str]:
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))

    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        text_nodes = [
            node.text
            for node in paragraph.findall(".//w:t", namespace)
            if node.text
        ]
        text = normalize_text("".join(text_nodes))
        if text:
            paragraphs.append(text)
    return paragraphs


def extract_pdf_paragraphs(path: Path) -> list[str]:
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=True,
        text=True,
        capture_output=True,
    )
    lines = [normalize_text(line) for line in result.stdout.splitlines()]
    paragraphs = []
    buffer = []
    for line in lines:
        if not line:
            if buffer:
                paragraphs.append(normalize_text(" ".join(buffer)))
                buffer = []
            continue
        buffer.append(line)
    if buffer:
        paragraphs.append(normalize_text(" ".join(buffer)))
    return [paragraph for paragraph in paragraphs if paragraph]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def is_literature_heading(value: str) -> bool:
    return bool(re.search(r"^(список\s+литературы|литература|источники|references)\b", value, re.I))


def split_body_and_literature(paragraphs: list[str]) -> tuple[list[str], list[str]]:
    body = []
    literature = []
    in_literature = False

    for paragraph in paragraphs:
        if is_literature_heading(paragraph):
            in_literature = True
            continue
        if in_literature:
            literature.append(paragraph)
        else:
            body.append(paragraph)

    return body, literature


def remove_duplicate_title(paragraphs: list[str], title: str) -> list[str]:
    title_key = normalize_text(title).lower()
    cleaned = []
    for paragraph in paragraphs:
        paragraph_key = normalize_text(paragraph).lower().strip(".")
        if paragraph_key == title_key:
            continue
        cleaned.append(paragraph)
    return cleaned


def first_lead(paragraphs: list[str]) -> str:
    for paragraph in paragraphs:
        if len(paragraph) >= 120:
            return paragraph
    return paragraphs[0] if paragraphs else "Материал подготовлен для раздела коллективной монографии."


def paragraph_to_html(paragraph: str) -> str:
    escaped = html.escape(paragraph)
    if looks_like_heading(paragraph):
        return f"<h3>{escaped}</h3>"
    return f"<p>{escaped}</p>"


def looks_like_heading(paragraph: str) -> bool:
    if len(paragraph) > 110:
        return False
    if paragraph.endswith((".", ";", ",")):
        return False
    if re.match(r"^\d+(\.\d+)*\.?\s+\S+", paragraph):
        return True
    return paragraph.isupper() and len(paragraph) > 8


def literature_to_html(items: list[str]) -> str:
    if not items:
        return "<li>Список литературы уточняется при редакционной подготовке материала.</li>"
    return "\n".join(f"<li>{html.escape(item)}</li>" for item in items)


def render_article(article: dict, paragraphs: list[str]) -> str:
    body, literature = split_body_and_literature(remove_duplicate_title(paragraphs, article["title"]))
    lead = first_lead(body)
    body_html = "\n".join(paragraph_to_html(paragraph) for paragraph in body)
    literature_html = literature_to_html(literature)
    today = date.today().strftime("%d.%m.%Y")

    return f"""<!doctype html>
<html lang="ru">
  <head>
    <meta charset="utf-8" />
    <title>{html.escape(article['title'])}</title>
    <style>
      @page {{ size: A4; margin: 20mm; }}
      :root {{
        --ink: #111111;
        --muted: #555555;
        --line: #b8b8b8;
        --soft: #f2f2f2;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        color: var(--ink);
        background: #ffffff;
        font-family: "Liberation Serif", "Times New Roman", serif;
        font-size: 14pt;
        line-height: 1.5;
      }}
      .page {{
        position: relative;
        min-height: 252mm;
        padding-bottom: 16mm;
        page-break-after: always;
      }}
      .page:last-child {{ page-break-after: auto; }}
      .header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12mm;
        padding-bottom: 5mm;
        border-bottom: 1px solid var(--line);
      }}
      .chapter-label {{
        font-family: Arial, Helvetica, sans-serif;
        font-size: 9pt;
        font-weight: 700;
        letter-spacing: 0;
        text-transform: uppercase;
      }}
      .chapter-title {{
        margin-top: 1.5mm;
        font-family: Arial, Helvetica, sans-serif;
        font-size: 11pt;
        font-weight: 700;
      }}
      .brand img {{ display: block; width: 34mm; height: auto; }}
      .section-number {{
        margin: 11mm 0 2mm;
        font-family: Arial, Helvetica, sans-serif;
        font-size: 10pt;
        font-weight: 700;
        text-transform: uppercase;
      }}
      h1, h2, h3 {{
        font-family: Arial, Helvetica, sans-serif;
        color: #000000;
        line-height: 1.12;
      }}
      h1 {{ margin: 0 0 6mm; font-size: 22pt; }}
      h2 {{ margin: 10mm 0 3mm; font-size: 15pt; }}
      h3 {{ margin: 6mm 0 2mm; font-size: 12.5pt; }}
      p {{
        margin: 0 0 3.2mm;
        text-align: justify;
        text-indent: 10mm;
      }}
      a {{ color: #000000; text-decoration: underline; }}
      .lead {{ color: #222222; font-size: 14pt; }}
      .meta-grid {{
        display: grid;
        grid-template-columns: 44mm 1fr;
        gap: 2mm 5mm;
        margin: 6mm 0 8mm;
        padding: 4mm;
        border: 1px solid var(--line);
      }}
      .meta-grid dt {{
        font-family: Arial, Helvetica, sans-serif;
        color: var(--muted);
        font-weight: 700;
      }}
      .meta-grid dd {{ margin: 0; }}
      .section-toc {{
        margin: 8mm 0;
        padding: 5mm;
        border: 1px solid var(--line);
        background: #ffffff;
      }}
      .section-toc h2 {{ margin-top: 0; }}
      .section-toc ol {{
        margin-bottom: 0;
        margin-left: 0;
        list-style: none;
      }}
      .section-toc a {{ text-decoration: none; }}
      .body-text p {{ text-indent: 10mm; }}
      .resource-list {{
        margin: 5mm 0 0;
        padding: 0;
        list-style: none;
        counter-reset: resources;
      }}
      .resource-list li {{
        display: grid;
        grid-template-columns: 56mm 1fr;
        gap: 3mm;
        margin-bottom: 2.6mm;
        padding-bottom: 2.6mm;
        border-bottom: 1px solid var(--line);
        counter-increment: resources;
      }}
      .resource-list li::before {{
        content: counter(resources) ". " attr(data-name);
        font-family: Arial, Helvetica, sans-serif;
        font-weight: 700;
      }}
      .resource-link {{ overflow-wrap: anywhere; }}
      .resource-note {{
        margin-top: 6mm;
        color: var(--muted);
        font-size: 11pt;
        text-indent: 0;
      }}
      .literature {{ margin-left: 7mm; }}
      .footer {{
        position: absolute;
        right: 0;
        bottom: 0;
        left: 0;
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 8mm;
        padding-top: 4mm;
        border-top: 1px solid var(--line);
        color: var(--muted);
        font-family: Arial, Helvetica, sans-serif;
        font-size: 8.5pt;
      }}
      .page-mark {{ white-space: nowrap; }}
    </style>
  </head>
  <body>
    <section class="page">
      <header class="header">
        <div>
          <div class="chapter-label">Коллективная монография «Цифровые Параллели»</div>
          <div class="chapter-title">Глава {html.escape(article['chapter_number'])}. {html.escape(article['chapter_title'])}</div>
        </div>
        <div class="brand"><img src="file://{LOGO_PATH}" alt="Digital Parallels" /></div>
      </header>

      <div class="section-number">Раздел {html.escape(article['section_number'])}</div>
      <h1>{html.escape(article['title'])}</h1>
      <p class="lead">{html.escape(lead)}</p>

      <dl class="meta-grid">
        <dt>Статус версии</dt>
        <dd>Редакционная версия</dd>
        <dt>Дата обновления</dt>
        <dd>{today}</dd>
        <dt>Источник</dt>
        <dd>{html.escape(article['source'].name)}</dd>
      </dl>

      <nav class="section-toc" aria-label="Оглавление раздела">
        <h2>Оглавление раздела</h2>
        <ol>
          <li><a href="#main-text">1. Основной текст</a></li>
          <li><a href="#resources">2. Связанные ресурсы</a></li>
          <li><a href="#literature">3. Список литературы</a></li>
        </ol>
      </nav>

      <h2 id="main-text">1. Основной текст</h2>
      <div class="body-text">
        {body_html}
      </div>

      <footer class="footer">
        <div>Авторы и резюме: ссылка на общий список авторов DNS</div>
        <div class="page-mark">DNS · раздел {html.escape(article['section_number'])}</div>
      </footer>
    </section>

    <section class="page">
      <header class="header">
        <div>
          <div class="chapter-label">Коллективная монография «Цифровые Параллели»</div>
          <div class="chapter-title">Связанные ресурсы раздела</div>
        </div>
        <div class="brand"><img src="file://{LOGO_PATH}" alt="Digital Parallels" /></div>
      </header>

      <h2 id="resources">2. Связанные ресурсы</h2>
      <ol class="resource-list">
        <li data-name="Опубликованный раздел"><span class="resource-link">ссылка на полный текст раздела</span></li>
        <li data-name="Оглавление DNS"><span class="resource-link">ссылка на актуальное оглавление монографии</span></li>
        <li data-name="Дискуссия по теме"><span class="resource-link">ссылка на обсуждение раздела</span></li>
        <li data-name="Мероприятия DP-Club"><span class="resource-link">ссылка на лекции, семинары и встречи</span></li>
        <li data-name="Материалы раздела"><span class="resource-link">ссылка на хранилище файлов и приложений</span></li>
        <li data-name="Авторы и резюме"><span class="resource-link">ссылка на общий список авторов DNS</span></li>
      </ol>
      <p class="resource-note">Действующие ссылки добавляются при публикации раздела.</p>

      <h2 id="literature">3. Список литературы</h2>
      <ol class="literature">
        {literature_html}
      </ol>

      <footer class="footer">
        <div>Авторы и резюме: ссылка на общий список авторов DNS</div>
        <div class="page-mark">DNS · раздел {html.escape(article['section_number'])}</div>
      </footer>
    </section>
  </body>
</html>
"""


def convert_html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    subprocess.run(
        [
            "google-chrome",
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--no-pdf-header-footer",
            "--allow-file-access-from-files",
            f"--print-to-pdf={pdf_path}",
            str(html_path),
        ],
        check=True,
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for article in ARTICLES:
        source = article["source"]
        if source.suffix.lower() == ".docx":
            paragraphs = extract_docx_paragraphs(source)
        elif source.suffix.lower() == ".pdf":
            paragraphs = extract_pdf_paragraphs(source)
        else:
            raise ValueError(f"Unsupported source format: {source}")

        html_text = render_article(article, paragraphs)
        html_path = OUTPUT_DIR / f"{article['slug']}.html"
        pdf_path = OUTPUT_DIR / f"{article['slug']}.pdf"
        html_path.write_text(html_text, encoding="utf-8")
        convert_html_to_pdf(html_path.resolve(), pdf_path.resolve())
        print(f"created {pdf_path}")


if __name__ == "__main__":
    main()
