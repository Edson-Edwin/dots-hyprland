"""Bounded PDF jobs; write finished results beside the first source."""
import ctypes
import ctypes.util
import errno
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

from PIL import Image, ImageOps
from convert import IMAGES

OPS = {"combine", "extract", "split", "each", "left", "right"}
MAX_PAGES = 1000
MAX_PARTS = 250


def page_count(path):
    cmd = subprocess.run(["pdfinfo", path], capture_output=True, timeout=12,
                         env={**os.environ, "LC_ALL": "C"})
    data = cmd.stdout.decode(errors="replace")
    pages = re.search(r"^Pages:\s+(\d+)", data, re.M)
    if cmd.returncode or not pages or re.search(r"^Encrypted:\s+yes", data, re.M):
        raise ValueError(f"Cannot use {path.name}: invalid, encrypted, or unreadable PDF.")
    return int(pages[1])


def groups(spec, count):
    """Comma joins pages in order; semicolon starts another output."""
    if len(spec) > 6000:
        raise ValueError("Page range is too long.")
    result = []
    total = 0
    for part in spec.split(";"):
        pages = []
        for token in part.split(","):
            m = re.fullmatch(r"\s*(\d{1,5})(?:\s*-\s*(\d{1,5}))?\s*", token)
            if not m:
                raise ValueError("Use page numbers like 1-3,5. Separate output files with a semicolon.")
            a, b = int(m[1]), int(m[2] or m[1])
            if min(a,b)<1 or max(a,b)>count:
                raise ValueError(f"Pages must be between 1 and {count}.")
            step = 1 if a<=b else -1
            total += abs(b-a)+1
            if total>MAX_PAGES:
                raise ValueError(f"Limit: {MAX_PAGES} output pages per job.")
            pages.extend(range(a,b+step,step))
        result.append(pages)
    if len(result)>MAX_PARTS:
        raise ValueError(f"Limit: {MAX_PARTS} split files per job.")
    return result


def qpdf(*args):
    name = ctypes.util.find_library("qpdf")
    if not name:
        raise ValueError("Install qpdf-libs to use PDF tools.")
    run = ctypes.CDLL(name).qpdfjob_run_from_argv
    run.argtypes = [ctypes.POINTER(ctypes.c_char_p)]
    run.restype = ctypes.c_int
    argv = [b"qpdf", *(os.fsencode(x) for x in args), None]
    if run((ctypes.c_char_p * len(argv))(*argv)) != 0:
        raise ValueError("PDF processing failed. Check the source files; no result was published.")


def publish(tmp, folder, name, directory=False):
    # Applies to files AND directories; never replace an existing user's output.
    rename = ctypes.CDLL(None, use_errno=True).renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    for i in range(1,10001):
        extra = "" if i==1 else f" ({i})"
        target = folder / (name + extra + ("" if directory else ".pdf"))
        if not rename(-100,os.fsencode(tmp),-100,os.fsencode(target),1):
            return target
        code = ctypes.get_errno()
        if code!=errno.EEXIST:
            raise OSError(code,os.strerror(code))
    raise ValueError("Too many outputs with that name.")


def image_page(path, dest):
    with Image.open(path) as im:
        if im.width*im.height>40_000_000 or getattr(im,"n_frames",1)!=1:
            raise ValueError(f"{path.name}: choose a single-frame image under 40 megapixels.")
        rgba=ImageOps.exif_transpose(im).convert("RGBA")
        page=Image.new("RGB",rgba.size,"white")
        page.paste(rgba,mask=rgba.getchannel("A"))
        page.save(dest,format="PDF",resolution=150,quality=95)


def execute(paths, op, spec=""):
    files=[Path(p).absolute() for p in paths]
    if op not in OPS or not 1<=len(files)<=100:
        raise ValueError("Select between 1 and 100 files.")
    for p in files:
        if not p.is_file() or p.is_symlink() or p.suffix.lower()[1:] not in IMAGES|{"pdf"}:
            raise ValueError("Choose regular local image or PDF files.")
    first=files[0]
    if op!="combine" and (len(files)!=1 or first.suffix.lower()!=".pdf"):
        raise ValueError("Select a single PDF for page tools.")
    with TemporaryDirectory(prefix=".ii-pdf-",dir=first.parent) as stage:
        t=Path(stage); out=t/"result.pdf"
        if op=="combine":
            args=[];total=0
            for i,p in enumerate(files):
                if p.suffix.lower()==".pdf":total+=page_count(p)
                else:
                    tmp=t/f"image-{i}.pdf";image_page(p,tmp);p=tmp;total+=1
                if total>MAX_PAGES:raise ValueError(f"Limit: {MAX_PAGES} pages per job.")
                args.extend([p,"1-z"])
            qpdf("--empty","--pages",*args,"--",out)
            if page_count(out)!=total:raise ValueError("Output page count did not match.")
            return publish(out,first.parent,first.stem+" - combined")
        count=page_count(first)
        if op in ("left","right"):
            qpdf(first,"--rotate="+("+90" if op=="right" else "-90"),out)
            if page_count(out)!=count:raise ValueError("Incomplete rotation.")
            return publish(out,first.parent,first.stem+" - rotated")
        if op=="each":
            if count>MAX_PARTS:raise ValueError(f"Limit: {MAX_PARTS} separate files.")
            parts=[[i] for i in range(1,count+1)]
        else:parts=groups(spec,count)
        if op=="extract" and len(parts)!=1:raise ValueError("Use Split for multiple output files.")
        directory=t/"parts";directory.mkdir()
        for i,nums in enumerate(parts,1):
            output=directory/f"Part {i:03}.pdf"
            qpdf("--empty","--pages",first,",".join(map(str,nums)),"--",output)
            if page_count(output)!=len(nums):raise ValueError("Incomplete extracted pages.")
        if op=="extract":return publish(output,first.parent,first.stem+" - pages")
        return publish(directory,first.parent,first.stem+" - split",True)


if __name__=="__main__":
    import resource
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_CPU,(110,120))
    resource.setrlimit(resource.RLIMIT_FSIZE,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    try:
        job=json.load(sys.stdin)
        print(json.dumps({"output":str(execute(job["files"],job["op"],job.get("spec","")))}))
    except Exception as err:
        print(json.dumps({"error":str(err)}));sys.exit(1)
