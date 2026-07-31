import tempfile
import unittest
from pathlib import Path

from scripts.sync_upstreams import SyncError, safe_child, sync_mapping


class SyncMappingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.destination = self.root / "destination"
        self.source.mkdir()
        self.destination.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def test_adds_and_updates_images_only(self):
        self.write(self.source / "new.png", b"new")
        self.write(self.source / "changed.jpg", b"upstream")
        self.write(self.source / "ignored.json", b"not an image")
        self.write(self.destination / "changed.jpg", b"old")

        summary = sync_mapping(
            self.source, self.destination, dry_run=False, delete=False
        )

        self.assertEqual((summary.added, summary.updated, summary.deleted), (1, 1, 0))
        self.assertEqual((self.destination / "new.png").read_bytes(), b"new")
        self.assertEqual((self.destination / "changed.jpg").read_bytes(), b"upstream")
        self.assertFalse((self.destination / "ignored.json").exists())

    def test_dry_run_does_not_write(self):
        self.write(self.source / "new.png", b"new")

        summary = sync_mapping(
            self.source, self.destination, dry_run=True, delete=False
        )

        self.assertTrue(summary.changed)
        self.assertFalse((self.destination / "new.png").exists())

    def test_delete_removes_only_managed_image_files(self):
        self.write(self.source / "kept.png", b"same")
        self.write(self.destination / "kept.png", b"same")
        self.write(self.destination / "obsolete.webp", b"old")
        self.write(self.destination / "md5.json", b"{}")

        summary = sync_mapping(
            self.source, self.destination, dry_run=False, delete=True
        )

        self.assertEqual(summary.deleted, 1)
        self.assertFalse((self.destination / "obsolete.webp").exists())
        self.assertTrue((self.destination / "md5.json").exists())

    def test_empty_source_is_rejected(self):
        with self.assertRaises(SyncError):
            sync_mapping(self.source, self.destination, dry_run=False, delete=False)


class PathSafetyTests(unittest.TestCase):
    def test_safe_child_rejects_parent_traversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(SyncError):
                safe_child(Path(temporary), "../outside", "test path")


if __name__ == "__main__":
    unittest.main()
