# llms-txt-generator

Erzeugt eine [`llms.txt`](https://llmstxt.org) aus der `sitemap.xml` deiner Website. Ein einzelnes Python-Skript, ohne Abhängigkeiten.

Eine `llms.txt` gibt KI-Systemen wie ChatGPT, Claude oder Perplexity einen kuratierten Überblick über die wichtigsten Seiten einer Website. Sie ist kein Google-Rankingfaktor, hilft aber dabei, Inhalte für KI-Suche klar und eindeutig zu strukturieren.

## Was es anders macht

Viele Generatoren kopieren einfach die Sitemap. Dieser prüft jede Seite vorher:

- **noindex-Seiten fliegen raus** (Meta-Robots und `X-Robots-Tag`)
- **Weiterleitungen werden aufgelöst**, doppelte Ziele erscheinen nur einmal
- **Fremde Canonicals werden respektiert**: Seiten, die auf eine andere URL zeigen, werden nicht gelistet
- **Fehlerseiten** (alles außer Status 200) werden übersprungen
- **Gruppierung nach Pfad**: `/guides/...` landet unter `## Guides`, Seiten ohne Unterordner unter `## Seiten`
- Titel und Beschreibung kommen aus `<title>` und `meta description`, der Markenname am Titelende wird entfernt

## Installation

Python 3.9 oder neuer, sonst nichts:

```bash
git clone https://github.com/elumcraft/llms-txt-generator.git
cd llms-txt-generator
```

## Verwendung

```bash
# Ausgabe in der Konsole
python3 llms_txt_generator.py https://www.example.com

# Direkt in eine Datei schreiben
python3 llms_txt_generator.py https://www.example.com -o llms.txt

# Eigener Name, eigene Kurzbeschreibung, Guides als optional markieren
python3 llms_txt_generator.py https://www.example.com \
  --name "Beispiel GmbH" \
  --summary "Webdesign und SEO für KMU in Österreich, Deutschland und der Schweiz." \
  --optional Guides \
  -o llms.txt

# Lokale Sitemap-Datei statt Abruf
python3 llms_txt_generator.py https://www.example.com --sitemap ./sitemap.xml
```

| Option | Bedeutung |
|---|---|
| `--sitemap` | Eigene Sitemap-URL oder lokale Datei. Standard: `<url>/sitemap.xml`. Sitemap-Indizes werden unterstützt. |
| `-o`, `--output` | Zieldatei. Standard: Ausgabe auf stdout. |
| `--name` | Überschrift (H1). Standard: Titel der Startseite. |
| `--summary` | Kurzbeschreibung als Zitat unter der H1. Standard: meta description der Startseite. |
| `--optional` | Abschnitt unter `## Optional` einordnen (mehrfach möglich). |
| `--max` | Maximale Anzahl URLs. Standard: 500. |
| `--workers` | Parallele Abrufe. Standard: 8. |

## Beispielausgabe

```markdown
# Beispiel GmbH

> Webdesign und SEO für KMU in Österreich, Deutschland und der Schweiz.

## Seiten
- [Webdesign](https://www.example.com/): Schnelle Websites für KMU.
- [Kontakt](https://www.example.com/kontakt): Schreiben Sie uns.

## Optional
- [SEO Guide](https://www.example.com/guides/seo): SEO einfach erklärt.
```

## Tipps

- Die erzeugte Datei ist ein **Startpunkt**. Am besten von Hand nachschärfen: wichtigste Leistungen nach oben, unwichtige Seiten (Impressum, AGB) streichen.
- Die Datei gehört ins Root-Verzeichnis: `https://www.example.com/llms.txt`.
- Optional im `<head>` verlinken: `<link rel="help" type="text/plain" href="/llms.txt">`.

## Tests

```bash
python3 -m unittest discover tests
```

Die Tests starten einen lokalen Server und brauchen keinen Internetzugang.

## English

Generates an [`llms.txt`](https://llmstxt.org) file from your `sitemap.xml`. Single-file Python, no dependencies. Skips noindex pages, resolves redirects, respects canonicals, drops error pages and groups URLs by their first path segment. Usage: `python3 llms_txt_generator.py https://www.example.com -o llms.txt`.

## Lizenz

MIT, siehe [LICENSE](LICENSE).

Entwickelt von [elumcraft](https://www.elumcraft.com), Webentwicklung, technisches SEO und Sichtbarkeit in KI-Suche für KMU in Österreich, Deutschland und der Schweiz.
