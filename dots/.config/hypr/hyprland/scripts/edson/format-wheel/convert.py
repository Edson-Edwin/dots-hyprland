"""Local, no-overwrite conversions for the Dolphin format wheel."""
import os
import re
import tempfile
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED
from PIL import Image, ImageOps

IMAGES = {"jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff", "gif"}
def choices(src):
    ext = src.suffix.lower().lstrip(".")
    if ext == "pdf":
        return {"docx": "Editable text", "txt": "Extract text", "png": "First page", "jpg": "First page"}
    if ext in IMAGES:
        return {k:v for k,v in {"png":"Lossless", "jpg":"Photo", "webp":"Compact", "pdf":"Document"}.items()
                if k != ("jpg" if ext == "jpeg" else ext)}
    return {}


def info(src, fmt):
    if src.suffix.lower() == ".pdf":
        if fmt in ("jpg","png"): return "Only page 1 will be saved as an image."
        return "Extract selectable text from all pages. Layout and images are not preserved; this is not OCR."
    if fmt in ("jpg", "pdf"): return "Transparent areas will have a white background."
    return "A new image will be created from the original."


def output_name(src, fmt, index=1):
    stem = src.stem + (" - page 1" if src.suffix.lower() == ".pdf" and fmt in ("png","jpg") else "")
    return src.with_name(stem + (f" ({index})" if index>1 else "") + "." + fmt)


def tool(cmd):
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=40)
    if r.returncode:
        raise ValueError("The PDF could not be read. It may be damaged or password-protected.")


def word(text, out):
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    ET.register_namespace("w",w)
    def tag(t):return "{"+w+"}"+t
    doc=ET.Element(tag("document")); body=ET.SubElement(doc,tag("body"))
    pages=text.rstrip("\f").split("\f")
    for i,page in enumerate(pages):
        if i:
            run=ET.SubElement(ET.SubElement(body,tag("p")),tag("r"))
            ET.SubElement(run,tag("br"),{tag("type"):"page"})
        for line in page.splitlines():
            r=ET.SubElement(ET.SubElement(body,tag("p")),tag("r"))
            ET.SubElement(r,tag("t"),{"{http://www.w3.org/XML/1998/namespace}space":"preserve"}).text=re.sub(r"[^\t\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]","",line)
    with ZipFile(out,"w",ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr('word/document.xml',ET.tostring(doc,encoding='utf-8',xml_declaration=True))


def convert(src, fmt):
    src=Path(src).absolute()
    if not src.is_file() or src.is_symlink() or fmt not in choices(src):
        raise ValueError("Choose a supported local file and format.")
    with tempfile.TemporaryDirectory(prefix=".ii-format-",dir=src.parent) as td:
        tmp=Path(td); out=tmp/("output."+fmt)
        if src.suffix.lower()==".pdf" and fmt in ("txt","docx"):
            textfile=tmp/"text.txt"
            tool(["pdftotext","-layout","-enc","UTF-8",src,textfile])
            if textfile.stat().st_size>12*1024**2: raise ValueError("Extracted text exceeds the 12 MiB limit.")
            text=textfile.read_text()
            if not text.strip():raise ValueError("No selectable text in this PDF. Use a page image or an OCR tool.")
            if fmt=="docx":word(text,out)
            else:os.replace(textfile,out)
        elif src.suffix.lower()==".pdf":
            tool(["pdftoppm","-f","1","-l","1","-singlefile","-scale-to","2400",
                  "-png" if fmt=="png" else "-jpeg",src,tmp/"output"])
        else:
            with Image.open(src) as im:
                if getattr(im,"n_frames",1)!=1:raise ValueError("Animated or multipage images are not converted by this wheel.")
                if im.width*im.height > 40_000_000:raise ValueError("Image exceeds the 40 megapixel limit.")
                im=ImageOps.exif_transpose(im).convert("RGBA")
                if fmt in ("jpg","pdf"):
                    bg=Image.new("RGB",im.size,"white");bg.paste(im,mask=im.getchannel("A"));im=bg
                im.save(out, **({"quality":93} if fmt in ("jpg","webp","pdf") else {}))
        if not out.is_file() or not out.stat().st_size:raise ValueError("Converter produced no output.")
        os.chmod(out,0o600)
        # Publish only finished bytes; a race or duplicate can never overwrite a prior copy.
        for i in range(1,10001):
            destination=output_name(src,fmt,i)
            try:os.link(out,destination);return destination
            except FileExistsError:pass
        raise ValueError("Too many copies with this filename.")


if __name__=="__main__":
    import resource,sys,json
    resource.setrlimit(resource.RLIMIT_AS,(1536*1024**2,1536*1024**2))
    resource.setrlimit(resource.RLIMIT_FSIZE,(256*1024**2,256*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(45,50))
    try:
        print(json.dumps({"output":str(convert(Path(sys.argv[1]),sys.argv[2]))}))
    except Exception as e:
        print(json.dumps({"error":str(e)}));sys.exit(1)
