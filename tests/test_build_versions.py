"""Keep historical content separate from the current build template."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class VersionSourcesTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.current = self.root / "current"
        self.version = self.root / "version"
        spec = importlib.util.spec_from_file_location(
            "build_versions", Path(__file__).resolve().parents[1] / "docs/sphinx_doc/build_versions.py"
        )
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)
        patched = patch.object(self.builder, "REPO_ROOT", self.current)
        patched.start()
        self.addCleanup(patched.stop)

    def write(self, root, name, content):
        path = root / "docs/sphinx_doc" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_refreshes_support_without_copying_current_content(self):
        self.write(self.current, "source/index.rst", "New guide index")
        self.write(self.current, "source/docs_index_ZH.rst", "New Chinese index")
        self.write(self.current, "source/docs/ProcessData.md", "Current generated guide")
        self.write(self.current, "source/README.md", "Current collected README")
        self.write(self.current, "source/extra_assets.yaml", "assets: [new]")
        self.write(self.current, "source/conf.py", "new config")
        self.write(self.current, "source/_static/help.md", "shared asset")
        self.write(self.current, "_templates/package.rst_t", "new template")
        self.write(self.current, "build/index.html", "generated output")
        originals = {
            "source/index.rst": "Old guide index",
            "source/docs_index_ZH.rst": "Old Chinese index",
            "source/guides/old.md": "Version-specific guide",
            "source/extra_assets.yaml": "assets: [old]",
        }
        for name, content in originals.items():
            self.write(self.version, name, content)
        self.write(self.version, "source/conf.py", "obsolete config")
        self.write(self.version, "source/obsolete_extension.py", "obsolete extension")

        self.builder.copy_docs_source_to(self.version)
        result = self.version / "docs/sphinx_doc"
        for name, content in originals.items():
            self.assertEqual((result / name).read_text(), content)
        self.assertEqual((result / "source/conf.py").read_text(), "new config")
        self.assertEqual((result / "source/_static/help.md").read_text(), "shared asset")
        self.assertEqual((result / "_templates/package.rst_t").read_text(), "new template")
        for name in ("source/docs/ProcessData.md", "source/README.md", "source/obsolete_extension.py", "build"):
            self.assertFalse((result / name).exists(), name)

    def test_template_indices_are_available_for_versions_without_docs(self):
        self.write(self.current, "source/index.rst", "Default index")
        self.write(self.current, "source/conf.py", "new config")
        self.builder.copy_docs_source_to(self.version)
        self.assertEqual(
            (self.version / "docs/sphinx_doc/source/index.rst").read_text(), "Default index"
        )


if __name__ == "__main__":
    unittest.main()
