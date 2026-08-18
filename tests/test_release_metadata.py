import json
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "robot-sltp-pro"


class ReleaseMetadataTests(unittest.TestCase):
    def test_desktop_version_is_consistent_across_build_systems(self):
        package = json.loads((DESKTOP / "package.json").read_text(encoding="utf-8"))
        tauri = json.loads((DESKTOP / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
        with (DESKTOP / "src-tauri" / "Cargo.toml").open("rb") as handle:
            cargo = tomllib.load(handle)

        package_lock = json.loads((DESKTOP / "package-lock.json").read_text(encoding="utf-8"))
        with (DESKTOP / "src-tauri" / "Cargo.lock").open("rb") as handle:
            cargo_lock = tomllib.load(handle)
        cargo_lock_version = next(item["version"] for item in cargo_lock["package"] if item["name"] == "robot-sltp-pro")

        versions = {
            "npm": package["version"],
            "npm_lock": package_lock["packages"][""]["version"],
            "tauri": tauri["version"],
            "cargo": cargo["package"]["version"],
            "cargo_lock": cargo_lock_version,
        }
        self.assertEqual(len(set(versions.values())), 1, versions)

    def test_repository_release_docs_match_desktop_version(self):
        version = json.loads((DESKTOP / "package.json").read_text(encoding="utf-8"))["version"]
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

        self.assertIn(f"Latest release — v{version}", readme)
        self.assertIn(f"ROBOT.SLTP.Pro_{version}_x64-setup.exe", readme)
        self.assertIn(f"## v{version}", changelog)
        self.assertTrue((ROOT / "docs" / f"RELEASE_v{version}.md").is_file())

    def test_runtime_version_comes_from_cargo_metadata(self):
        source = (DESKTOP / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
        self.assertIn('version: env!("CARGO_PKG_VERSION")', source)


if __name__ == "__main__":
    unittest.main()
