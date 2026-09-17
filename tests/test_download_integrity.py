import hashlib
import io
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from vocari import runtime_deps as deps
from vocari.tts import silero_provider as silero


def digest(data):
    return hashlib.sha256(data).hexdigest()


def response(data, length=None):
    stream = io.BytesIO(data)
    stream.headers = {"Content-Length": str(len(data) if length is None else length)}
    return stream


class DownloadIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_verified_download_replaces_file(self):
        path = self.root / "model.pt"
        path.write_bytes(b"old")
        with patch.object(deps.urllib.request, "urlopen", return_value=response(b"verified")):
            deps.download_raw_file("https://example.test/model", path, lambda *_: None, sha256=digest(b"verified"))
        self.assertEqual(path.read_bytes(), b"verified")
        self.assertFalse(path.with_suffix(".pt.part").exists())

    def test_wrong_hash_and_truncation_preserve_previous_file(self):
        path = self.root / "model.pt"
        for data, length in ((b"tampered", 8), (b"expected", 100)):
            with self.subTest(data=data):
                path.write_bytes(b"old")
                with patch.object(deps.urllib.request, "urlopen", return_value=response(data, length)), \
                        self.assertLogs("vocari.runtime_deps", level="ERROR"), self.assertRaises(ValueError):
                    deps.download_raw_file("https://example.test/model", path, lambda *_: None, sha256=digest(b"expected"))
                self.assertEqual(path.read_bytes(), b"old")
                self.assertFalse(path.with_suffix(".pt.part").exists())

    def archive(self, filename="package/data.txt"):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as zf:
            zf.writestr(filename, b"verified")
        return data.getvalue()

    def test_archive_verified_before_existing_install_is_touched(self):
        archive = self.archive()
        dep = deps.RuntimeDep("Test", "engine", "https://example.test/file.zip", 1, digest(archive))
        target = self.root / "engine"
        target.mkdir()
        (target / "keep").write_bytes(b"old install")
        with patch.object(deps, "RUNTIME_DEPS_DIR", self.root), \
                patch.object(deps.urllib.request, "urlopen", return_value=response(b"tampered")), \
                patch.object(zipfile.ZipFile, "extractall") as extract, \
                self.assertLogs("vocari.runtime_deps", level="ERROR"), self.assertRaises(ValueError):
            deps.download(dep, lambda *_: None)
        extract.assert_not_called()
        self.assertEqual((target / "keep").read_bytes(), b"old install")
        self.assertEqual(list(self.root.iterdir()), [target])

    def test_verified_install_marker_and_old_marker_migration(self):
        archive = self.archive()
        dep = deps.RuntimeDep("Test", "engine", "https://example.test/file.zip", 1, digest(archive))
        with patch.object(deps, "RUNTIME_DEPS_DIR", self.root), \
                patch.object(deps.urllib.request, "urlopen", return_value=response(archive)), \
                patch.object(deps, "ensure_on_path"):
            deps.download(dep, lambda *_: None)
            self.assertTrue(deps.is_downloaded(dep))
            self.assertEqual((self.root / "engine/package/data.txt").read_bytes(), b"verified")
            deps._marker(dep).write_text(str(dep.version))
            self.assertFalse(deps.is_downloaded(dep))

    def test_archive_traversal_is_rejected(self):
        tar = io.BytesIO()
        with tarfile.open(fileobj=tar, mode="w:gz") as tf:
            entry = tarfile.TarInfo("../outside.txt")
            entry.size = 3
            tf.addfile(entry, io.BytesIO(b"bad"))
        for ext, data in (("zip", self.archive("../outside.txt")), ("tar.gz", tar.getvalue())):
            dep = deps.RuntimeDep("Test", "engine", f"https://example.test/file.{ext}", 1, digest(data))
            with patch.object(deps, "RUNTIME_DEPS_DIR", self.root), \
                    patch.object(deps.urllib.request, "urlopen", return_value=response(data)), \
                    self.assertLogs("vocari.runtime_deps", level="ERROR"), self.assertRaises((ValueError, tarfile.TarError)):
                deps.download(dep, lambda *_: None)
            self.assertFalse((self.root / "outside.txt").exists())
            self.assertFalse((self.root / "engine/.complete").exists())

    def test_cached_silero_model_is_checked_without_loading_repository(self):
        legacy = self.root / "snakers4_silero-models_master/src/silero/model/v4_ru.pt"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b"verified model")
        with patch.object(silero, "CACHE_DIR", self.root), \
                patch.dict(silero.MODEL_SHA256_BY_LANG, {"ru": digest(b"verified model")}), \
                patch.object(silero, "download_raw_file") as download:
            self.assertEqual(silero.SileroTTSProvider()._verified_model_path("ru"), legacy)
        download.assert_not_called()

    def test_bad_silero_content_never_reaches_package_importer(self):
        cached = self.root / "verified/v4_ru.pt"
        cached.parent.mkdir(parents=True)
        cached.write_bytes(b"tampered cache")
        torch = Mock()
        with patch.dict("sys.modules", {"torch": torch}), \
                patch.object(silero, "ensure_on_path"), \
                patch.object(silero, "CACHE_DIR", self.root), \
                patch.object(deps.urllib.request, "urlopen", return_value=response(b"tampered download")), \
                self.assertLogs("vocari", level="WARNING"), self.assertRaises(ValueError):
            silero.SileroTTSProvider().preload("ru")
        torch.package.PackageImporter.assert_not_called()
        torch.hub.load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
