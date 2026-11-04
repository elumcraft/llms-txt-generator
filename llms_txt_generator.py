#!/usr/bin/env python3
"""
llms-txt-generator – erzeugt eine llms.txt (llmstxt.org) aus der sitemap.xml einer Website.

Ohne Abhängigkeiten, nur Python-Standardbibliothek (3.9+).

Was es anders macht als ein reiner Sitemap-Dump:
  * Seiten mit noindex (Meta-Tag oder X-Robots-Tag) werden übersprungen
  * Weiterleitungen werden aufgelöst, Duplikate entfernt
  * Canonical-Ziele haben Vorrang, Seiten mit fremdem Canonical fallen raus
  * Gruppierung nach dem ersten Pfadsegment (z. B. /guides/ -> "Guides")
  * Titel und Beschreibung kommen aus <title> und meta description

Beispiel:
  python3 llms_txt_generator.py https://www.example.com -o llms.txt
  python3 llms_txt_generator.py https://www.example.com --sitemap ./sitemap.xml --max 100

(c) elumcraft e.U. – MIT License – https://www.elumcraft.com
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import gzip
import html
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable
from xml.etree import ElementTree as ET

__version__ = "1.0.0"
USER_AGENT = f"llms-txt-generator/{__version__} (+https://github.com/elumcraft/llms-txt-generator)"
SM_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


@dataclass
class Page:
    url: str
    title: str = ""
    description: str = ""
    canonical: str = ""
    noindex: bool = False
    status: int = 0
    error: str = ""


class _HeadParser(HTMLParser):
    """Liest title, meta description, robots und canonical aus dem HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.robots = ""
        self.canonical = ""
        self.og_title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = a.get("name", "").lower()
            prop = a.get("property", "").lower()
            if name == "description" and not self.description:
                self.description = a.get("content", "")
            elif name in ("robots", "googlebot"):
                self.robots += " " + a.get("content", "").lower()
            elif prop == "og:title" and not self.og_title:
                self.og_title = a.get("content", "")
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.canonical = a.get("href", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def fetch(url: str, timeout: float = 15.0) -> tuple[int, str, dict, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            if r.headers.get("Content-Encoding") == "gzip" or url.endswith(".gz"):
                try:
                    body = gzip.decompress(body)
                except OSError:
                    pass
            return r.status, r.geturl(), dict(r.headers), body
    except urllib.error.HTTPError as e:
        return e.code, url, dict(e.headers or {}), b""


def parse_sitemap(xml_bytes: bytes) -> tuple[list[str], list[str]]:
    """Gibt (Seiten-URLs, Unter-Sitemaps) zurück."""
    root = ET.fromstring(xml_bytes)
    locs = [el.text.strip() for el in root.iter(f"{SM_NS}loc") if el.text]
    if root.tag == f"{SM_NS}sitemapindex":
        return [], locs
    return locs, []


def collect_urls(base: str, sitemap: str | None, limit: int) -> list[str]:
    queue = [sitemap or urllib.parse.urljoin(base, "/sitemap.xml")]
    seen, urls = set(), []
    while queue and len(urls) < limit:
        src = queue.pop(0)
        if src in seen:
            continue
        seen.add(src)
        if re.match(r"^https?://", src):
            status, _, _, body = fetch(src)
            if status != 200:
                print(f"Warnung: {src} liefert Status {status}", file=sys.stderr)
                continue
        else:
            with open(src, "rb") as fh:
                body = fh.read()
        pages, children = parse_sitemap(body)
        urls.extend(pages)
        queue.extend(children)
    return list(dict.fromkeys(urls))[:limit]


def inspect(url: str) -> Page:
    p = Page(url=url)
    try:
        status, final, headers, body = fetch(url)
    except Exception as e:  # Netzwerkfehler sollen den Lauf nicht abbrechen
        p.error = str(e)
        return p
    p.status, p.url = status, final
    xrobots = " ".join(v for k, v in headers.items() if k.lower() == "x-robots-tag").lower()
    if status != 200:
        return p
    parser = _HeadParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    p.title = clean(parser.title or parser.og_title)
    p.description = clean(parser.description)
    p.canonical = urllib.parse.urljoin(final, parser.canonical) if parser.canonical else ""
    p.noindex = "noindex" in parser.robots or "noindex" in xrobots
    return p


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def strip_brand(title: str, site_name: str) -> str:
    """Entfernt einen angehängten Markennamen wie ' - elumcraft' oder ' | Firma'."""
    if not site_name:
        return title
    pattern = rf"\s*[-|–—·:]\s*{re.escape(site_name)}\s*$"
    return re.sub(pattern, "", title, flags=re.I) or title


def norm(u: str) -> str:
    parts = urllib.parse.urlsplit(u)
    path = parts.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc.lower(), path, parts.query, ""))


def section_of(url: str) -> str:
    seg = urllib.parse.urlsplit(url).path.strip("/").split("/")[0]
    if not seg or "/" not in urllib.parse.urlsplit(url).path.strip("/"):
        return "Seiten"
    return seg.replace("-", " ").title()


def build(base: str, pages: Iterable[Page], site_name: str, summary: str, optional: set[str]) -> str:
    kept: dict[str, Page] = {}
    for p in pages:
        if p.status != 200 or p.noindex or p.error:
            continue
        if p.canonical and norm(p.canonical) != norm(p.url):
            continue  # Seite verweist per Canonical auf eine andere URL
        kept.setdefault(norm(p.url), p)

    home = kept.get(norm(base))
    name = site_name or (home.title if home else urllib.parse.urlsplit(base).netloc)
    desc = summary or (home.description if home else "")

    groups: dict[str, list[Page]] = {}
    for p in kept.values():
        groups.setdefault(section_of(p.url), []).append(p)

    out = [f"# {name}", ""]
    if desc:
        out += [f"> {desc}", ""]
    order = sorted(groups, key=lambda g: (g in optional, g != "Seiten", g))
    for g in order:
        heading = "Optional" if g in optional else g
        out.append(f"## {heading}")
        for p in sorted(groups[g], key=lambda x: (urllib.parse.urlsplit(x.url).path.count("/"), x.url)):
            title = strip_brand(p.title, site_name) or p.url
            line = f"- [{title}]({p.url})"
            if p.description:
                line += f": {p.description}"
            out.append(line)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Erzeugt eine llms.txt aus der sitemap.xml einer Website.")
    ap.add_argument("url", help="Basis-URL der Website, z. B. https://www.example.com")
    ap.add_argument("--sitemap", help="Eigene Sitemap-URL oder lokale Datei (Standard: <url>/sitemap.xml)")
    ap.add_argument("-o", "--output", default="-", help="Zieldatei (Standard: Ausgabe auf stdout)")
    ap.add_argument("--name", default="", help="Name der Website/Marke für die H1 (Standard: Titel der Startseite)")
    ap.add_argument("--summary", default="", help="Kurzbeschreibung (Standard: meta description der Startseite)")
    ap.add_argument("--optional", action="append", default=[], help="Abschnitt als 'Optional' markieren, z. B. --optional Guides")
    ap.add_argument("--max", type=int, default=500, help="Maximale Anzahl an URLs (Standard: 500)")
    ap.add_argument("--workers", type=int, default=8, help="Parallele Abrufe (Standard: 8)")
    ap.add_argument("--version", action="version", version=__version__)
    args = ap.parse_args(argv)

    base = args.url.rstrip("/") + "/"
    urls = collect_urls(base, args.sitemap, args.max)
    if not urls:
        print("Keine URLs in der Sitemap gefunden.", file=sys.stderr)
        return 1
    with cf.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        pages = list(ex.map(inspect, urls))

    text = build(base, pages, args.name, args.summary, set(args.optional))
    listed = sum(1 for line in text.splitlines() if line.startswith("- ["))
    if args.output == "-":
        sys.stdout.write(text)
    else:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(f"{listed} von {len(pages)} URLs übernommen. Übersprungen wurden noindex, fremde Canonicals, "
          f"Weiterleitungs-Duplikate und Fehlerseiten.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
