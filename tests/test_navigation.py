"""Build real Sphinx sites to verify navigation across document layouts."""
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from html.parser import HTMLParser

from sphinx.application import Sphinx


class Navigation(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.region = None
        self.links = {"tabs": [], "sidebar": [], "prev-next": []}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav" and attrs.get("class") in ("navbar-sections", "sidebar-nav", "prev-next"):
            self.region = {"navbar-sections": "tabs", "sidebar-nav": "sidebar", "prev-next": "prev-next"}[attrs["class"]]
        if tag == "a" and self.region:
            self.links[self.region].append(attrs)

    def handle_endtag(self, tag):
        if tag == "nav":
            self.region = None


class NavigationTests(unittest.TestCase):
    def build_site(self, legacy=False, language="en", api="api", builder="html"):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        src = base / "source"
        src.mkdir()
        root = "index_ZH" if language == "zh_CN" else "index"
        docs = "docs_index_ZH" if language == "zh_CN" else "docs_index"
        (src / "conf.py").write_text(
            f"html_theme = 'data_juicer_theme'\nroot_doc = {root!r}\nlanguage = {language!r}\n"
            f"html_theme_options = {{'api_root': {api!r}}}\n"
        )
        def write(name, text):
            p = src / (name + ".rst")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        entries = f"   {docs}" if legacy else "   guide/start"
        if api:
            entries += f"\n   {api}"
        write(root, "Home\n====\n\n.. toctree::\n   :hidden:\n\n" + entries + "\n")
        if legacy:
            write(docs, "Docs\n====\n\n.. toctree::\n   :caption: Guides\n\n   guide/start\n")
        write("guide/start", "Start guide\n===========\n")
        if api:
            write(api, "API\n===\n\n.. toctree::\n\n   reference/module\n")
            write("reference/module", "Module reference\n================\n\n.. toctree::\n\n   nested/class\n")
            write("reference/nested/class", "Class reference\n===============\n")
        warnings = StringIO()
        app = Sphinx(str(src), str(src), str(base / "html"), str(base / "doctrees"),
                     builder, status=StringIO(), warning=warnings, freshenv=True)
        app.build(force_all=True)
        # Multiple applications in one process produce Sphinx registration warnings.
        self.assertEqual(app.statuscode, 0, warnings.getvalue())
        def read(name):
            path = name + ".html" if builder == "html" else name + "/index.html"
            if builder == "dirhtml" and name == root:
                path = "index.html"
            return Navigation((base / "html" / path).read_text()).links
        return app, read, root

    def test_flat_legacy_and_translated_sections(self):
        for legacy, language, api, builder in [
            (False, "en", "api", "html"),
            (True, "en", "api", "html"),
            (True, "zh_CN", "api", "html"),
            (False, "en", "reference_index", "dirhtml"),
        ]:
            with self.subTest(legacy=legacy, language=language, builder=builder):
                app, read, root = self.build_site(legacy, language, api, builder)
                for page in [root, "guide/start"]:
                    links = read(page)
                    self.assertEqual(len(links["tabs"]), 2)
                    self.assertIn("active", links["tabs"][0]["class"])
                    self.assertFalse(any("module" in a["href"] or "class" in a["href"] or api in a["href"] for a in links["sidebar"]))
                    self.assertTrue(any("start" in a["href"] or (page == "guide/start" and a["href"] in ("", "#")) for a in links["sidebar"]))
                for page in [api, "reference/module", "reference/nested/class"]:
                    links = read(page)
                    self.assertIn("active", links["tabs"][1]["class"])
                    self.assertFalse(any("guide" in a["href"] for a in links["sidebar"] + links["prev-next"]))
                self.assertIn(api, app.env.toctree_includes[root])
                self.assertIn("reference/module", app.env.toctree_includes[api])

    def test_site_without_api_retains_navigation(self):
        _, read, root = self.build_site(api="")
        self.assertEqual(read(root)["tabs"], [])
        self.assertTrue(any("start" in a["href"] for a in read(root)["sidebar"]))


if __name__ == "__main__":
    unittest.main()
