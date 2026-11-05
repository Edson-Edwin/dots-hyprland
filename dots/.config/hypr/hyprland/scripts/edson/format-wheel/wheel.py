"""An on-demand, transparent radial file converter for Dolphin / Hyprland."""
import fcntl
import json
import math
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
import cairo
import gi
gi.require_version("Gdk","3.0")
gi.require_version("Gtk","3.0")
gi.require_version("GtkLayerShell","0.1")
gi.require_version("PangoCairo","1.0")
from gi.repository import Gdk, GLib, Gtk, GtkLayerShell, Pango, PangoCairo
from convert import choices, info, output_name

R=135; INNER=52
COL={"surface_container_high":"#29282b","surface_container":"#222124","on_surface":"#f2eeee","on_surface_variant":"#c9c4cb","primary":"#bfcae8","on_primary":"#192841","outline_variant":"#555058"}
try:
    p=Path(os.getenv("XDG_STATE_HOME") or Path.home()/".local/state")/"quickshell/user/generated/colors.json"
    COL.update({k:v for k,v in json.loads(p.read_text()).items() if k in COL and isinstance(v,str) and re.fullmatch("#[0-9a-fA-F]{6}",v)})
except (ValueError,OSError): pass

def hypr(cmd):
    return json.loads(subprocess.check_output(["hyprctl","-j",cmd],timeout=2))

def color(c,key):
    v=COL[key];c.set_source_rgb(*(int(v[i:i+2],16)/255 for i in (1,3,5)))

def label(c,x,y,s,size,key,bold=False,width=100):
    l=PangoCairo.create_layout(c);font=Pango.FontDescription()
    font.set_family("Sans");font.set_absolute_size(size*Pango.SCALE)
    if bold:font.set_weight(Pango.Weight.BOLD)
    l.set_font_description(font);l.set_text(s,-1);l.set_width(int(width*Pango.SCALE))
    l.set_ellipsize(Pango.EllipsizeMode.END);l.set_alignment(Pango.Alignment.CENTER)
    _,h=l.get_pixel_size();c.move_to(x-width/2,y-h/2);color(c,key);PangoCairo.show_layout(c,l)


class Wheel:
    def __init__(self,file):
        self.file=file;self.options=choices(file);self.items=list(self.options)
        if file.suffix.lower()==".pdf":
            self.options["pages"]="PDF tools"
            self.items=list(self.options)
        self.sel=None;self.card=None;self.busy=False
        w=self.win=Gtk.Window();w.set_title("Convert format");w.set_app_paintable(True)
        visual=w.get_screen().get_rgba_visual()
        if visual:w.set_visual(visual)
        GtkLayerShell.init_for_window(w);GtkLayerShell.set_namespace(w,"ii-format-wheel")
        GtkLayerShell.set_layer(w,GtkLayerShell.Layer.OVERLAY);GtkLayerShell.set_exclusive_zone(w,-1)
        for edge in (GtkLayerShell.Edge.TOP,GtkLayerShell.Edge.BOTTOM,GtkLayerShell.Edge.LEFT,GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(w,edge,True)
        GtkLayerShell.set_keyboard_mode(w,GtkLayerShell.KeyboardMode.EXCLUSIVE)
        pt=hypr("cursorpos");monitors=hypr("monitors")
        d=Gdk.Display.get_default();mon=d.get_primary_monitor() or d.get_monitor(0)
        for i in range(d.get_n_monitors()):
            m=d.get_monitor(i);g=m.get_geometry()
            if g.x<=pt['x']<g.x+g.width and g.y<=pt['y']<g.y+g.height:
                mon=m;break
        # GTK Wayland may present a different logical origin from Hyprland.
        # Identify the physical output using its connector when possible.
        for hm in monitors:
            if not hm.get("focused"):continue
            for i in range(d.get_n_monitors()):
                m=d.get_monitor(i)
                if m.get_model()==hm["name"]:mon=m;break
        GtkLayerShell.set_monitor(w,mon);g=mon.get_geometry()
        hm=next((m for m in monitors if m['name']==mon.get_model()),None)
        self.px=pt['x']-(hm['x'] if hm else g.x);self.py=pt['y']-(hm['y'] if hm else g.y)
        self.overlay=Gtk.Overlay();w.add(self.overlay)
        self.area=Gtk.DrawingArea();self.overlay.add(self.area);self.area.set_can_focus(True)
        self.area.add_events(Gdk.EventMask.POINTER_MOTION_MASK|Gdk.EventMask.BUTTON_PRESS_MASK)
        self.area.connect("draw",self.draw);self.area.connect("motion-notify-event",self.motion)
        self.area.connect("button-press-event",self.press);w.connect("key-press-event",self.key)
        w.connect("destroy",lambda *_: Gtk.main_quit())
        self.area.get_accessible().set_name("Convert format. Use the arrow keys to select a format, then Enter.")
        css=Gtk.CssProvider()
        css.load_from_data(('''#convert-card {background-color:%s;color:%s;border:1px solid %s;border-radius:17px;padding:18px;}
#convert-card label {color:%s;} #convert-card button {padding:7px 13px;border-radius:10px;}
#convert-yes {background-image:none;background-color:%s;} #convert-card #convert-yes label {color:%s;}''' % tuple(COL[k] for k in ("surface_container_high","on_surface","outline_variant","on_surface","primary","on_primary"))).encode())
        Gtk.StyleContext.add_provider_for_screen(w.get_screen(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        w.show_all();self.area.grab_focus()
    def center(self):
        return (max(R+8,min(self.area.get_allocated_width()-R-8,self.px)),
                max(R+8,min(self.area.get_allocated_height()-R-8,self.py)))
    def hit(self,x,y):
        cx,cy=self.center();dx=x-cx;dy=y-cy
        if not INNER+3<=math.hypot(dx,dy)<=R:return None
        return int(((math.atan2(dy,dx)+math.pi/2)%(2*math.pi))/(2*math.pi)*len(self.items))%len(self.items)
    def draw(self,area,c):
        c.set_operator(cairo.OPERATOR_SOURCE);c.set_source_rgba(0,0,0,0);c.paint();c.set_operator(cairo.OPERATOR_OVER)
        if self.card:return False
        cx,cy=self.center();n=len(self.items)
        for i,fmt in enumerate(self.items):
            a=-math.pi/2+i*math.tau/n;b=a+math.tau/n;mid=(a+b)/2
            selected=self.sel==i
            c.new_path();c.arc(cx,cy,R,a+.017,b-.017);c.arc_negative(cx,cy,INNER+3,b-.017,a+.017);c.close_path()
            color(c,"primary" if selected else "surface_container_high");c.fill_preserve()
            color(c,"primary" if selected else "outline_variant");c.set_line_width(1);c.stroke()
            x=cx+math.cos(mid)*93;y=cy+math.sin(mid)*93
            label(c,x,y-7,fmt.upper(),16,"on_primary" if selected else "on_surface",True,70)
            label(c,x,y+12,self.options[fmt],10,"on_primary" if selected else "on_surface_variant",width=68)
        c.new_path();c.arc(cx,cy,INNER-1,0,math.tau);color(c,"surface_container");c.fill_preserve();color(c,"outline_variant");c.stroke()
        label(c,cx,cy-9,"CONVERT",9,"primary",True,86)
        label(c,cx,cy+8,self.file.suffix[1:].upper(),17,"on_surface",True,84)
        return False
    def motion(self,w,e):
        if not self.card:
            i=self.hit(e.x,e.y)
            if i!=self.sel:self.sel=i;w.queue_draw()
        return False
    def press(self,w,e):
        if self.card:return False
        i=self.hit(e.x,e.y)
        if e.button==1 and i is not None:self.confirm(self.items[i])
        else:self.win.destroy()
        return True
    def key(self,w,e):
        if self.busy:return True
        if e.keyval==Gdk.KEY_Escape:self.win.destroy();return True
        if self.card:return False
        if e.keyval in (Gdk.KEY_Right,Gdk.KEY_Down,Gdk.KEY_Left,Gdk.KEY_Up):
            delta=1 if e.keyval in (Gdk.KEY_Right,Gdk.KEY_Down) else -1
            self.sel=(0 if self.sel is None else (self.sel+delta)%len(self.items));self.area.queue_draw();return True
        if e.keyval in (Gdk.KEY_Return,Gdk.KEY_KP_Enter) and self.sel is not None:
            self.confirm(self.items[self.sel]);return True
        return False
    def confirm(self,fmt):
        if fmt=="pages":
            os.execl(sys.executable,sys.executable,str(Path(__file__).with_name("pdf_dialog.py")),str(self.file))
        card=self.card=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);card.set_name("convert-card")
        card.set_halign(Gtk.Align.START);card.set_valign(Gtk.Align.START)
        wid=min(360,self.area.get_allocated_width()-18)
        card.set_size_request(wid,-1)
        cx,cy=self.center()
        card.set_margin_start(max(8,min(int(cx-wid/2),self.area.get_allocated_width()-wid-8)))
        card.set_margin_top(max(8,min(int(cy-100),self.area.get_allocated_height()-260)))
        title=Gtk.Label(label=f"Create a {fmt.upper()} copy?");title.set_xalign(0);card.add(title)
        msg=Gtk.Label(label=f"{self.file.name}\n→ {output_name(self.file,fmt).name}\n\n{info(self.file,fmt)}")
        msg.set_line_wrap(True);msg.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR);msg.set_max_width_chars(40);msg.set_xalign(0);card.add(msg)
        row=Gtk.Box(spacing=8);row.set_halign(Gtk.Align.END);card.add(row)
        cancel=Gtk.Button(label="Cancel");cancel.connect("clicked",lambda *_:self.win.destroy());row.add(cancel)
        yes=Gtk.Button(label="Yes, create copy");yes.set_name("convert-yes");row.add(yes)
        def start(*_):
            if self.busy:return
            self.busy=True;row.set_sensitive(False);msg.set_text("Converting…")
            def worker():
                try:
                    r=subprocess.run([sys.executable,str(Path(__file__).with_name("convert.py")),str(self.file),fmt],
                                     capture_output=True,text=True,timeout=60)
                    result=json.loads(r.stdout)
                    txt=("Created "+Path(result["output"]).name if "output" in result else result["error"])
                except (ValueError,OSError,subprocess.SubprocessError):
                    txt="Conversion stopped or exceeded its limit. No original was changed."
                GLib.idle_add(done,txt)
            threading.Thread(target=worker,daemon=True).start()
        def done(txt):
            self.busy=False;row.set_sensitive(True);yes.hide();cancel.set_label("Done");msg.set_text(txt);cancel.grab_focus()
            return False
        yes.connect("clicked",start);self.overlay.add_overlay(card);card.show_all();self.area.queue_draw();cancel.grab_focus()

if __name__=="__main__":
    if len(sys.argv)>2:
        os.execv(sys.executable,[sys.executable,str(Path(__file__).with_name("pdf_dialog.py")),*sys.argv[1:]])
    if len(sys.argv)==2:
        file=Path(sys.argv[1]).absolute()
        if file.is_file() and not file.is_symlink() and choices(file):
            lock=(Path(os.environ["XDG_RUNTIME_DIR"])/"ii-format-wheel.lock").open("a")
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:sys.exit(0)
            Wheel(file);Gtk.main()
