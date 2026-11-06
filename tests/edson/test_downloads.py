"""Test only temporary files; never use the user's real download directory."""
import os
import runpy
import time
from pathlib import Path
from tempfile import TemporaryDirectory

script = Path(__file__).with_name("organizer.py")
if not script.is_file():
    script = Path(__file__).resolve().parents[2] / "dots/.config/quickshell/ii/scripts/downloads-organizer/organizer.py"
sort_files = runpy.run_path(str(script))["sort_files"]

with TemporaryDirectory() as temp:
    d = Path(temp)
    (d/"pdf").mkdir()
    (d/"pdf/report.PDF").write_text("existing")
    (d/"report.PDF").write_text("new")
    (d/"foo.tar.gz").write_text("archive")
    (d/"LICENSE").touch()
    (d/".hidden").touch()
    (d/"ongoing.part").touch()
    (d/"fresh.zip").touch()
    (d/"a.iso").touch()
    (d/"a.iso.aria2").touch()
    (d/"outside").mkdir()
    (d/"txt").symlink_to(d/"outside", target_is_directory=True)
    (d/"note.txt").touch()
    (d/"link.png").symlink_to(d/"note.txt")
    for p in ("report.PDF", "foo.tar.gz", "LICENSE", "note.txt"):
        os.utime(d/p, (time.time()-300,)*2)
    moved, skipped, failed = sort_files(d, True)
    assert moved==3 and failed==1 and skipped>=3, (moved, skipped, failed)
    assert (d/"pdf/report.PDF").read_text()=="existing" and (d/"pdf/report (2).PDF").read_text()=="new"
    assert (d/"tar.gz/foo.tar.gz").exists() and (d/"No extension/LICENSE").exists()
    assert (d/"fresh.zip").exists() and not list((d/"outside").iterdir())
    assert (d/"link.png").is_symlink() and (d/"ongoing.part").exists() and (d/"a.iso").exists()
    (d/"txt").unlink()
    assert sort_files(d)[0]==2
    assert sort_files(d)[0]==0
print("PASS: manual/scheduled sorting, duplicate preservation, partial and recent file guards, symlinks, repeat runs")
