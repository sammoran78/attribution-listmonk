import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone
import upload


NOW = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
CONFIG = """[listmonk-drive]
type = drive
scope = drive.file
client_id = test-client
client_secret = test-secret
token = {"refresh_token":"test"}
[listmonk-backups]
type = crypt
remote = listmonk-drive:Mailing List Backups/encrypted
filename_encryption = standard
directory_name_encryption = true
password = test-obscured-password
password2 = test-obscured-salt
"""


class UploadSafety(unittest.TestCase):
    def setUp(self):
        directory = upload.DEPLOY / "backups"
        directory.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="test-drive-", dir=directory)
        assert Path(self.temp.name).resolve().is_relative_to(directory.resolve())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "secrets").mkdir()
        (self.root / "backups").mkdir()
        self.config = self.root / "secrets/rclone-backups.conf"
        self.config.write_text(CONFIG)
        self.config.chmod(0o600)
        for name in ["db-20261012T110000Z.dump", "uploads-20261012T110000Z.tar.gz"]:
            (self.root / "backups" / name).write_bytes(b"nonempty test backup")

    def test_plaintext_or_broad_scope_is_rejected(self):
        for config in [CONFIG.replace("type = crypt", "type = drive"),
                       CONFIG.replace("scope = drive.file", "scope = drive")]:
            self.config.write_text(config)
            with self.assertRaises(RuntimeError):
                upload.validate_config(self.config)

    def test_newest_incomplete_pair_does_not_fall_back(self):
        (self.root / "backups/db-20261012T113000Z.dump").write_bytes(b"partial")
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            upload.newest_pair(self.root / "backups", NOW)

    def test_stale_and_oversize_backups_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "stale"):
            upload.newest_pair(self.root / "backups", datetime(2026, 10, 15, tzinfo=timezone.utc))
        path = self.root / "backups/db-20261012T110000Z.dump"
        with path.open("wb") as output:
            output.truncate(upload.MAX_BYTES + 1)
        with self.assertRaisesRegex(RuntimeError, "guard"):
            upload.newest_pair(self.root / "backups", NOW)

    def test_failed_verification_never_prunes(self):
        commands = []
        def run(config, *args):
            commands.append(args)
            if args[0] == "about":
                return json.dumps({"free": 10000000})
            if args[0] == "check":
                raise RuntimeError("verification failed")
            return ""
        with self.assertRaisesRegex(RuntimeError, "verification failed"):
            upload.upload(self.root, NOW, run)
        self.assertEqual([args[0] for args in commands], ["about", "copy", "check"])
        self.assertFalse((self.root / "secrets/drive-backup-status.json").exists())

    def test_only_old_recognized_files_are_trashed_after_verification(self):
        commands = []
        def run(config, *args):
            commands.append(args)
            if args[0] == "about":
                return json.dumps({"free": 10000000})
            if args[0] == "lsjson":
                return json.dumps([{"Path": name} for name in [
                    "db-20260901T110000Z.dump", "uploads-20260901T110000Z.tar.gz",
                    "db-20261012T110000Z.dump", "other.txt", "../db-20260901T110000Z.dump",
                    "db-20269999T110000Z.dump", "db-20260901T110000Z.tar.gz"]])
            return ""
        state = upload.upload(self.root, NOW, run)
        self.assertEqual(state["old_files_moved_to_trash"], 2)
        deleted = [args for args in commands if args[0] == "deletefile"]
        self.assertTrue(all(args[-1] == "--drive-use-trash=true" for args in deleted))
        self.assertIn("--download", next(args for args in commands if args[0] == "check"))


if __name__ == "__main__":
    unittest.main()
