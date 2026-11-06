"""Actual conversions against an isolated temporary directory."""
import hashlib, sys, tempfile
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from PIL import Image
import cairo
base=Path(__file__).resolve().parents[2]/"dots/.config/hypr/hyprland/scripts/edson/format-wheel"
sys.path.insert(0,str(base if base.exists() else Path(__file__).parent))
from convert import convert

with tempfile.TemporaryDirectory() as t:
    d=Path(t); src=d/"Résumé's scan.pdf"
    surf=cairo.PDFSurface(str(src),300,200);ctx=cairo.Context(surf)
    for page in ("hello one","hello two"):
        ctx.move_to(25,55);ctx.show_text(page);surf.show_page()
    surf.finish()
    original=hashlib.sha256(src.read_bytes()).digest()
    for fmt in ('docx','txt','png','jpg'):
        out=convert(src,fmt)
        if fmt=='docx':
            with ZipFile(out) as z:
                root=ET.fromstring(z.read("word/document.xml"));text=" ".join(root.itertext())
                assert 'hello one' in text and 'hello two' in text
        if fmt=='txt':assert 'hello two' in out.read_text()
        if fmt in ('png','jpg'):
            with Image.open(out) as im:assert im.format==('PNG' if fmt=='png' else 'JPEG')
    assert original==hashlib.sha256(src.read_bytes()).digest()
    img=d/"Photo '01.png";Image.new("RGBA",(64,32),(255,0,0,0)).save(img)
    collision=img.with_suffix(".jpg");collision.write_bytes(b"keep")
    out=convert(img,"jpg");assert " (2)" in out.name and collision.read_bytes()==b"keep"
    with Image.open(out) as im:assert im.getpixel((0,0))==(255,255,255)
    assert convert(img,"pdf").read_bytes().startswith(b"%PDF")
    with Image.open(convert(img,"webp")) as im:assert im.format=="WEBP"
    blank=convert(img,"pdf")
    try:convert(blank,"docx")
    except ValueError as e:assert 'selectable text' in str(e)
    else:raise AssertionError("image-only PDF must not claim to contain extracted text")
print("PASS: multipage text and editable DOCX, real PDF page images, image conversion, duplicate preservation, original bytes and scan-only error")
