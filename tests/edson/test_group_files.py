"""Only exercise temporary images; originals, ZIP members and output names must survive collisions."""
import sys,tempfile
from pathlib import Path
from zipfile import ZipFile
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'dots/.config/hypr/hyprland/scripts/edson/format-wheel'))
from pdf_jobs import execute
with tempfile.TemporaryDirectory() as t:
    d=Path(t);a=d/'a';b=d/'b';a.mkdir();b.mkdir()
    files=[a/'Photo.png',b/'Photo.png']
    for p,col in zip(files,['red','blue']):Image.new('RGB',(12,8),col).save(p)
    inputs=[p.read_bytes() for p in files]
    archive=execute(files,'zip')
    with ZipFile(archive) as z:
        assert z.namelist()==['Photo.png','Photo (2).png']
        assert [z.read(name) for name in z.namelist()]==inputs
    for fmt in ['jpg','webp','png']:
        folder=execute(files,fmt)
        assert sorted(p.name for p in folder.iterdir())==[f'Photo (2).{fmt}',f'Photo.{fmt}']
        for f in folder.iterdir():
            with Image.open(f) as im:assert im.size==(12,8)
    txt=d/'Notes.txt';txt.write_text('sample')
    assert execute([files[0],txt],'list').read_text()=='Photo.png\nNotes.txt\n'
    with ZipFile(execute([txt,files[0]],'zip')) as z:assert z.read('Notes.txt')==b'sample'
    assert [p.read_bytes() for p in files]==inputs
print('PASS: archive bytes, all three batch image formats, collisions, original files')
