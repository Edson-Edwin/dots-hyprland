"""Review file order and page operations before starting a local PDF job."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import gi
gi.require_version("Gtk","3.0")
from gi.repository import GLib, Gtk
from pdf_jobs import groups, page_count

ACTIONS={"combine":"Combine into one PDF", "extract":"Extract or reorder pages",
         "split":"Split by page ranges", "each":"One file per page",
         "left":"Rotate all pages left", "right":"Rotate all pages right"}


class Dialog(Gtk.Window):
    def __init__(self, files):
        super().__init__(title="PDF tools")
        self.files=files;self.busy=False;self.count=None
        self.set_default_size(500,460);self.set_border_width(18)
        self.connect("delete-event",lambda *_: self.busy)
        self.connect("destroy",lambda *_: Gtk.main_quit())
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);self.add(box)
        self.mode=Gtk.ComboBoxText()
        single=len(files)==1 and files[0].suffix.lower()==".pdf"
        for key,label in ACTIONS.items():
            if single or key=="combine":self.mode.append(key,label)
        box.pack_start(self.mode,False,False,0)
        self.hint=Gtk.Label(xalign=0);self.hint.set_line_wrap(True);box.pack_start(self.hint,False,False,0)
        self.list=Gtk.ListBox();scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.list);box.pack_start(scroll,True,True,0)
        self.order=Gtk.Box(spacing=8);box.pack_start(self.order,False,False,0)
        for name,step in [("Move up",-1),("Move down",1)]:
            btn=Gtk.Button(label=name);btn.connect("clicked",lambda _,s=step:self.move(s));self.order.add(btn)
        self.range=Gtk.Entry();self.range.set_placeholder_text("Page ranges");box.pack_start(self.range,False,False,0)
        self.status=Gtk.Label(xalign=0);self.status.set_line_wrap(True);self.status.set_selectable(True)
        box.pack_start(self.status,False,False,0)
        self.create=Gtk.Button(label="Review and create…");self.create.connect("clicked",self.review)
        box.pack_end(self.create,False,False,0)
        self.refresh(0)
        self.mode.connect("changed",self.change);self.show_all();self.mode.set_active_id("extract" if single else "combine")
        if single:
            def check():
                try:value=page_count(files[0])
                except (ValueError,OSError,subprocess.SubprocessError):value=None
                GLib.idle_add(self.got_count,value)
            threading.Thread(target=check,daemon=True).start()

    def got_count(self,count):
        self.count=count
        if not self.busy:self.change()
        return False

    def change(self,*_):
        k=self.mode.get_active_id()
        self.range.set_visible(k in ("extract","split"));self.order.set_visible(len(self.files)>1)
        hints={"combine":"Each image becomes one page. PDFs keep their page order. Arrange the inputs from top to bottom.",
               "extract":"Enter pages in the order you want, for example 3,1-2. Leave out unwanted pages.",
               "split":"Separate output files with semicolons: 1-3;4-6. Each group becomes one PDF.",
               "each":"Create a new folder containing one numbered PDF per page.",
               "left":"Turn every page counterclockwise by 90° in a new PDF.",
               "right":"Turn every page clockwise by 90° in a new PDF."}
        self.hint.set_text((f"{self.count} pages. " if self.count else "")+hints[k])
        self.range.set_placeholder_text("Example: 1-3;4-6" if k=="split" else "Example: 3,1-2")

    def refresh(self,i):
        for child in self.list.get_children():self.list.remove(child)
        for j,p in enumerate(self.files,1):
            label=Gtk.Label(label=f"{j}.  {p.name}",xalign=0);label.set_margin_top(4);label.set_margin_bottom(4)
            self.list.add(label)
        self.list.show_all();self.list.select_row(self.list.get_row_at_index(i))

    def move(self,step):
        row=self.list.get_selected_row()
        if not row:return
        i=row.get_index();j=i+step
        if 0<=j<len(self.files):
            self.files[i],self.files[j]=self.files[j],self.files[i];self.refresh(j)

    def review(self,*_):
        k=self.mode.get_active_id();spec=self.range.get_text().strip()
        if k in ("extract","split"):
            try:
                parts=groups(spec,self.count or 10**5)
                if k=="extract" and len(parts)!=1:raise ValueError("Use Split for multiple output files.")
            except ValueError as exc:self.status.set_text(str(exc));return
        question=Gtk.MessageDialog(transient_for=self,modal=True,message_type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.YES_NO,text=ACTIONS[k]+"?")
        extra=f"\nPages: {spec}" if k in ("extract","split") else ""
        question.format_secondary_text(f"Create new output beside {self.files[0].name} in\n{self.files[0].parent}.{extra}\nThe originals will be kept.")
        question.set_default_response(Gtk.ResponseType.NO);answer=question.run();question.destroy()
        if answer!=Gtk.ResponseType.YES:return
        self.busy=True;self.create.set_sensitive(False);self.mode.set_sensitive(False)
        self.order.set_sensitive(False);self.range.set_sensitive(False)
        self.status.set_text("Creating PDF output…")
        payload=json.dumps({"files":[str(f) for f in self.files],"op":k,"spec":spec})
        def worker():
            try:
                run=subprocess.run([sys.executable,str(Path(__file__).with_name("pdf_jobs.py"))],
                                   input=payload,capture_output=True,text=True,timeout=150)
                result=json.loads(run.stdout)
                msg=("Created: "+result["output"]) if "output" in result else result["error"]
            except (ValueError,OSError,subprocess.SubprocessError):
                msg="The job stopped or exceeded its limit. The original files were not changed."
            GLib.idle_add(self.done,msg)
        threading.Thread(target=worker,daemon=True).start()

    def done(self,msg):
        self.busy=False;self.create.set_sensitive(True);self.mode.set_sensitive(True)
        self.order.set_sensitive(True);self.range.set_sensitive(True);self.status.set_text(msg)
        return False


if __name__=="__main__":
    GLib.set_prgname("ii-pdf-tools")
    files=[Path(s).absolute() for s in sys.argv[1:]]
    if files:
        Dialog(files);Gtk.main()
