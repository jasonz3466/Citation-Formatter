"""Checks that index.html actually contains everything script.js reaches for.

A missing id makes getElementById return null, and calling addEventListener on
null throws — which stops the whole script, not just that line. The page then
loads blank with no error visible unless you open the console.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "citation_formatter"
HTML = (PACKAGE / "templates" / "index.html").read_text()
JS = (PACKAGE / "static" / "script.js").read_text()
CSS = (PACKAGE / "static" / "style.css").read_text()


class TestTemplateHooks(unittest.TestCase):
    def test_every_id_the_script_uses_exists(self):
        # Match either quote style. The earlier check quietly missed most of script.js.
        wanted = {
            name
            for _, name in re.findall(r"""getElementById\((["'])([^"']+)\1\)""", JS)
            if "style" not in name
        }
        for name in sorted(wanted):
            with self.subTest(id=name):
                self.assertIn(f'id="{name}"', HTML)

    def test_the_three_output_panels_exist(self):
        for style in ("APA", "MLA", "Chicago"):
            self.assertIn(f'id="out-{style}"', HTML)
            self.assertIn(f'id="intext-{style}"', HTML)

    def test_every_class_the_script_queries_exists(self):
        wanted = set(re.findall(r'querySelectorAll?\("(\.[a-z-]+)[^"]*"\)', JS))
        for selector in sorted(wanted):
            with self.subTest(selector=selector):
                self.assertIn(selector[1:], HTML)

    def test_every_icon_reference_resolves(self):
        used = set(re.findall(r'href="(#i-[a-z]+)"', HTML)) | set(
            re.findall(r'"(#i-[a-z]+)"', JS)
        )
        for icon in sorted(used):
            with self.subTest(icon=icon):
                self.assertIn(f'id="{icon[1:]}"', HTML)

    def test_the_stylesheet_covers_the_generated_markup(self):
        # Classes the script writes into innerHTML never appear in the template,
        # so nothing else would catch a typo in them.
        for generated in ("word--guess", "library-item", "remove", "is-copied"):
            with self.subTest(css=generated):
                self.assertIn(generated, CSS)

    def test_no_duplicate_const_declarations(self):
        names = re.findall(r"^const (\w+)\s*=", JS, flags=re.M)
        duplicates = {n for n in names if names.count(n) > 1}
        self.assertEqual(
            duplicates, set(), f"redeclared, which is a fatal SyntaxError: {duplicates}"
        )

    def test_page_has_basic_project_metadata(self):
        self.assertIn('name="description"', HTML)
        self.assertIn("<title>QuickCite | Citation formatter</title>", HTML)

    def test_css_does_not_force_browser_zoom(self):
        self.assertNotRegex(CSS, r"(?m)^\s*zoom\s*:")

    def test_css_has_device_specific_layouts(self):
        for query in (
            "@media (min-width: 1500px)",
            "@media (max-width: 1080px)",
            "@media (max-width: 720px)",
            "@media (max-width: 480px)",
            "@media (max-width: 360px)",
        ):
            with self.subTest(query=query):
                self.assertIn(query, CSS)

    def test_source_cards_respond_to_their_own_width(self):
        self.assertIn("@container source-editor (min-width: 48rem)", CSS)
        self.assertIn("container-name: source-editor", CSS)

    def test_stylesheet_uses_the_quiet_workspace_palette(self):
        # These anchor colors keep the light and dark themes from drifting apart.
        for color in ("#f4f5f6", "#315f87", "#111418", "#8fb5d7"):
            with self.subTest(color=color):
                self.assertIn(color, CSS)

    def test_stylesheet_uses_the_larger_reading_scale(self):
        self.assertIn("font-size: clamp(19px, calc(18px + .22vw), 21px)", CSS)

    def test_css_supports_system_and_manual_themes(self):
        self.assertIn("@media (prefers-color-scheme: dark)", CSS)
        self.assertIn(':root[data-theme="dark"]', CSS)
        self.assertIn(':root[data-theme="light"]', CSS)

    def test_lookup_section_has_no_outer_card_outline(self):
        block = re.search(r"\.lookup-card\s*\{([^}]+)\}", CSS, flags=re.S)
        self.assertIsNotNone(block)
        self.assertIn("border: 0", block.group(1))
        self.assertIn("box-shadow: none", block.group(1))

    def test_uv_project_file_exists(self):
        self.assertTrue((ROOT / "pyproject.toml").is_file())
        self.assertTrue((ROOT / "uv.lock").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
