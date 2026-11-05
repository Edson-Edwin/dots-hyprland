"""Read generated pages back to verify page content, ordering, and no-overwrite behavior."""
from pathlib import Path
import hashlib,re,subprocess,sys,tempfile
import cairo
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"dots/.config/hypr/hyprland/scripts/edson/format-wheel"))
from pdf_jobs import execute,page_count,groups,qpdf

def pdf(p, labels):
    surf=cairo.PDFSurface(str(p),220,160);ctx=cairo.Context(surf)
    for label in labels:
        ctx.move_to(10,30);ctx.show_text(label);surf.show_page()
    surf.finish()

def labels(p):
    return re.findall(r'PAGE_[A-Z]',subprocess.check_output(["pdftotext",p,"-"],text=True))

with tempfile.TemporaryDirectory() as td:
    d=Path(td);one=d/"April '25.pdf";two=d/"Other.pdf"
    pdf(one,["PAGE_A","PAGE_B","PAGE_C"]);pdf(two,["PAGE_D"])
    red=d/"red.jpg";blue=d/"blue.png"
    Image.new("RGB",(120,80),"red").save(red);Image.new("RGB",(80,120),"blue").save(blue)
    original={p:hashlib.sha256(p.read_bytes()).digest() for p in d.iterdir()}

    out=execute([blue,red],"combine");assert page_count(out)==2
    for i,want in [(1,2),(2,0)]:
        data=subprocess.check_output(["pdftoppm","-f",str(i),"-l",str(i),"-singlefile","-scale-to","10",out])
        import io
        with Image.open(io.BytesIO(data)) as img:
            pixel=img.getpixel((2,2));assert pixel[want]>230 and sum(pixel)-pixel[want]<40,pixel
    merged=execute([two,one],"combine");assert labels(merged)==["PAGE_D","PAGE_A","PAGE_B","PAGE_C"]
    mixed=execute([two,blue,one],"combine");assert page_count(mixed)==5 and labels(mixed)==labels(merged)
    assert execute([two,one],"combine").name.endswith(" (3).pdf")
    extract=execute([one],"extract","3,2-1");assert labels(extract)==["PAGE_C","PAGE_B","PAGE_A"]
    split=execute([one],"split","1,3;2")
    assert [labels(p) for p in sorted(split.iterdir())]==[["PAGE_A","PAGE_C"],["PAGE_B"]]
    each=execute([one],"each");assert [labels(p) for p in sorted(each.iterdir())]==[["PAGE_A"],["PAGE_B"],["PAGE_C"]]
    for mode,angle in [('right',90),('left',270)]:
        rotated=execute([one],mode)
        assert page_count(rotated)==3 and re.search(fr'Page rot:\s+{angle}',subprocess.check_output(['pdfinfo',rotated],text=True))
    before=set(d.iterdir())
    for spec in ("0","4","2-9000","1;;2","1-",""):
        try:execute([one],"split",spec)
        except ValueError:pass
        else:raise AssertionError(spec)
    assert set(d.iterdir())==before
    locked=d/"locked.pdf";qpdf(one,"--encrypt","user","owner","256","--",locked)
    try:execute([locked],"each")
    except ValueError:pass
    else:raise AssertionError("accepted locked input")
    for p,digest in original.items():assert hashlib.sha256(p.read_bytes()).digest()==digest
print("PASS: JPEG/PNG page order, merge and mixed files, extraction, split groups, individual pages, rotation, invalid ranges, locked PDFs, collisions, original hashes")
