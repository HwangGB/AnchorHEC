#!/usr/bin/env python3
"""Build the checked-in GitHub Pages site with Python's standard library."""
import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def escaped(value):
    return html.escape(str(value), quote=True)


def url(value, *, local=False):
    if not value:
        return ""
    parts = urlparse(value)
    if parts.scheme in {"http", "https"} and parts.netloc:
        return escaped(value)
    if local and not parts.scheme and not parts.netloc and not value.startswith(("/", "\\")) and ".." not in Path(parts.path).parts and "\\" not in value:
        return escaped(value)
    raise ValueError(f"Expected an absolute HTTP(S) URL{' or a site-relative path' if local else ''}: {value!r}")


def resource_button(href, label, icon, *, local=False):
    content = f'<svg viewBox="0 0 24 24" aria-hidden="true">{icon}</svg>{escaped(label)}'
    if href:
        return f'<a class="button" href="{url(href, local=local)}">{content}</a>'
    return (f'<button class="button" type="button" disabled '
            f'title="{escaped(label)} link coming soon" '
            f'aria-label="{escaped(label)} (coming soon)">{content}</button>')


def bibtex_text(value):
    replacements = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_", "$": r"\$", "~": r"\~{}", "^": r"\^{}"}
    return "".join(replacements.get(char, char) for char in str(value))


def build(config_path, output):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    scenes = json.loads((ROOT / "docs/assets/data/scenes.json").read_text(encoding="utf-8"))
    authors = config.get("authors", [])
    affiliations = config.get("affiliations", [])
    affiliation_ids = {str(item["id"]) for item in affiliations}
    author_markup = []
    for author in authors:
        name = escaped(author["name"])
        if not author["name"].strip():
            raise ValueError("Author names must not be empty")
        if author.get("url"):
            name = f'<a href="{url(author["url"])}">{name}</a>'
        ids = [str(item) for item in author.get("affiliations", [])]
        if not set(ids) <= affiliation_ids:
            raise ValueError(f"Unknown affiliation for {author['name']}")
        markers = ids if len(affiliations) > 1 else []
        if author.get("corresponding"):
            markers = [*markers, "†"]
        if markers:
            name += f'<sup>{escaped(",".join(markers))}</sup>'
        author_markup.append(f'<span class="author">{name}</span>')
    author_block = ""
    if authors:
        author_block = '<div class="author-block"><p class="authors">' + " ".join(author_markup) + '</p>'
        if affiliations:
            entries = []
            for affiliation in affiliations:
                name = escaped(affiliation["name"])
                if affiliation.get("url"):
                    name = f'<a href="{url(affiliation["url"])}">{name}</a>'
                marker = f'<sup>{escaped(affiliation["id"])}</sup> ' if len(affiliations) > 1 else ""
                entries.append(f'<span>{marker}{name}</span>')
            author_block += '<p class="affiliations">' + " ".join(entries) + '</p>'
        if any(author.get("corresponding") for author in authors):
            author_block += '<p class="corresponding-note">† Corresponding author</p>'
        author_block += '</div>'

    arxiv_id = config.get("arxiv_id", "").strip()
    if arxiv_id and not re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", arxiv_id):
        raise ValueError("arxiv_id must be a real identifier such as YYMM.NNNNN, optionally with vN")
    arxiv_url = (config.get("arxiv_url") or "").strip() or (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "")
    paper_url = (config.get("paper_url") or "").strip()
    paper_href = paper_url or arxiv_url
    code_url = (config.get("code_url") or "").strip()
    paper_button = resource_button(paper_href, "Paper",
        '<path fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" d="M6 3h8l4 4v14H6Z M14 3v5h4 M9 12h6 M9 16h6"/>', local=True)
    code_button = resource_button(code_url, "Code",
        '<path fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" d="m8 7-5 5 5 5m8-10 5 5-5 5M14 4l-4 16"/>')

    citation = '<p class="citation-pending">Citation details will be added with the public preprint.</p>'
    bibtex = ""
    if authors and arxiv_id:
        author_names = " and ".join(bibtex_text(author.get("bibtex_name") or author["name"]) for author in authors)
        bibtex = (
            f"@misc{{anchorhec{int(config['year'])},\n"
            f"  title = {{{bibtex_text(config['title'])}}},\n"
            f"  author = {{{author_names}}},\n"
            f"  year = {{{int(config['year'])}}},\n"
            f"  eprint = {{{arxiv_id}}},\n"
            "  archivePrefix = {arXiv},\n"
            f"  url = {{https://arxiv.org/abs/{arxiv_id}}}\n"
            "}\n"
        )
        citation = '<div class="citation-box"><div class="citation-toolbar"><span>BibTeX</span><button class="text-link" id="copy-citation" type="button" aria-live="polite">Copy BibTeX</button></div>'
        citation += f'<pre><code id="bibtex">{escaped(bibtex)}</code></pre></div>'

    contact = ""
    email = config.get("contact_email", "").strip()
    if email:
        if not re.fullmatch(r"[^\s@?&#]+@[^\s@?&#]+\.[^\s@?&#]+", email):
            raise ValueError("contact_email must contain one plain email address")
        contact = f'<p class="contact-line">Contact: <a href="mailto:{escaped(email)}">{escaped(email)}</a></p>'

    metadata = [f'<meta name="citation_title" content="{escaped(config["title"])}">']
    metadata += [f'<meta name="citation_author" content="{escaped(author["name"])}">' for author in authors]
    if paper_url and urlparse(paper_url).scheme in {"http", "https"}:
        metadata.append(f'<meta name="citation_pdf_url" content="{url(paper_url)}">')
    if arxiv_id:
        metadata.append(f'<meta name="citation_arxiv_id" content="{escaped(arxiv_id)}">')

    canonical = config["canonical_url"].rstrip("/") + "/"
    values = {
        "TITLE": escaped(config["title"]), "DESCRIPTION": escaped(config["description"]),
        "CANONICAL_URL": url(canonical), "REPOSITORY_URL": url(config["repository_url"]),
        "STATUS": escaped(config["status"]), "YEAR": str(int(config["year"])),
        "ABSTRACT": escaped(config["abstract"]), "AUTHOR_BLOCK": author_block,
        "SCHOLAR_METADATA": "\n  ".join(metadata),
        "PAPER_BUTTON": paper_button, "CODE_BUTTON": code_button,
        "CITATION_BLOCK": citation, "CONTACT_BLOCK": contact,
        "SCENES_JSON": json.dumps(scenes, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace("&", "\\u0026"),
    }
    output.mkdir(parents=True, exist_ok=True)
    for filename in ("index.html", "credits.html"):
        source = (ROOT / "src" / filename).read_text(encoding="utf-8")
        rendered = re.sub(r"\{\{([A-Z_]+)\}\}", lambda match: values[match[1]], source)
        (output / filename).write_text(rendered, encoding="utf-8")
    citation_path = output / "assets/data/citation.bib"
    if bibtex:
        citation_path.parent.mkdir(parents=True, exist_ok=True)
        citation_path.write_text(bibtex, encoding="utf-8")
    elif citation_path.exists():
        citation_path.unlink()
    print(f"Built {output}/index.html and credits.html.")
    pending = []
    if not authors:
        pending.append("authors/affiliations")
    if not paper_href:
        pending.append("public paper/arXiv URL")
    if not email:
        pending.append("contact email")
    if pending:
        print("Awaiting confirmed details: " + ", ".join(pending) + ". These fields are hidden or marked as forthcoming.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "site.json")
    parser.add_argument("--output", type=Path, default=ROOT / "docs", help="HTML output directory; assets remain in docs/ for normal builds")
    args = parser.parse_args()
    build(args.config, args.output)
