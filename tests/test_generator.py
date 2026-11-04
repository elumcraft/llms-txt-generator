"""Tests mit einem lokalen Test-Server, ohne Internetzugriff: python3 -m unittest discover tests"""
import http.server
import os
import sys
import threading
import unittest

os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import llms_txt_generator as gen  # noqa: E402

PAGES = {
    "/": '<title>Webdesign - Beispiel</title><meta name="description" content="Schnelle Websites für KMU.">',
    "/kontakt": '<title>Kontakt - Beispiel</title><meta name="description" content="Schreiben Sie uns.">',
    "/guides/seo": '<title>SEO Guide - Beispiel</title><meta name="description" content="SEO einfach erklärt.">',
    "/intern": '<title>Intern</title><meta name="robots" content="noindex,nofollow">',
    "/kopie": '<title>Kopie</title><link rel="canonical" href="/kontakt">',
}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        base = f"http://127.0.0.1:{self.server.server_port}"
        if self.path == "/sitemap.xml":
            locs = "".join(f"<url><loc>{base}{p}</loc></url>" for p in list(PAGES) + ["/alt", "/fehlt"])
            body = f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>'
            return self._send(200, body, "application/xml")
        if self.path == "/alt":
            self.send_response(301)
            self.send_header("Location", "/kontakt")
            self.end_headers()
            return
        if self.path in PAGES:
            return self._send(200, f"<html><head>{PAGES[self.path]}</head><body></body></html>")
        return self._send(404, "nicht gefunden")

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class GeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}/"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def run_gen(self, *extra):
        out = os.path.join(os.path.dirname(__file__), "_out.txt")
        self.assertEqual(gen.main([self.base, "-o", out, "--name", "Beispiel", *extra]), 0)
        with open(out, encoding="utf-8") as fh:
            text = fh.read()
        os.remove(out)
        return text

    def test_structure_and_filters(self):
        text = self.run_gen()
        self.assertTrue(text.startswith("# Beispiel\n\n> Schnelle Websites für KMU."))
        self.assertIn("## Seiten", text)
        self.assertIn("## Guides", text)
        self.assertIn("- [SEO Guide](", text)  # Markenname entfernt
        self.assertIn("SEO einfach erklärt.", text)
        self.assertNotIn("Intern", text)  # noindex
        self.assertNotIn("Kopie", text)  # fremdes Canonical
        self.assertNotIn("/fehlt", text)  # 404
        self.assertEqual(text.count("/kontakt)"), 1)  # Weiterleitung /alt dedupliziert

    def test_optional_section(self):
        text = self.run_gen("--optional", "Guides")
        self.assertIn("## Optional", text)
        self.assertLess(text.index("## Seiten"), text.index("## Optional"))


if __name__ == "__main__":
    unittest.main()
