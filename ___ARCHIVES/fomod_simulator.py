# fomod_simulator.py
# Version 1.7.22 — Référence (Retour Google Translate + UI Stable/Légère)
"""
Simulateur FOMOD générique (tkinter)

Moteur :
- Analyse complète FOMOD (installStep / group / plugin)
- Déduplication stricte (signature profonde)
- Pré-sélection stricte basée sur Data (fileDependency uniquement)
- Installation simulée vers un dossier “Staging”
- Gestion des requiredInstallFiles et conditionalFileInstalls (STUB)

Interface :
- 3 colonnes rééquilibrées : 20 (Gauche) / 30 (Centre) / 50 (Droite).
- Traduction en ligne via Google Translate (nécessite connexion Internet).
- Fix Scrollbar Hauteur/Taille stable (auto-hide).
- Boutons de navigation élargis.
- Marge globale conservée.
- Taille d'exécutable compilé très réduite.

Optimisations/Ajustements:
- Centrage des fenêtres Toplevel (Infos mod, Aperçu image).
"""

import os
import re
import shutil
import zipfile
import tempfile
import subprocess
import webbrowser
from collections import Counter

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, Toplevel
from tkinter import font as tkfont

from PIL import Image, ImageTk
from lxml import etree

# -----------------------------------------------------------
#  OPTIONNEL : Googletrans pour la traduction
# -----------------------------------------------------------
try:
    from googletrans import Translator
    _HAS_TRANSLATOR = True
    _translator = Translator()
except Exception:
    _HAS_TRANSLATOR = False
    _translator = None


# -----------------------------------------------------------
#  PERMISSIONS
# -----------------------------------------------------------
def set_dir_perms(p: str):
    try: os.chmod(p, 0o777)
    except Exception: pass

def set_file_perms(p: str):
    try: os.chmod(p, 0o666)
    except Exception: pass

def set_tree_perms(root: str):
    for r, dnames, fnames in os.walk(root):
        set_dir_perms(r)
        for d in dnames: set_dir_perms(os.path.join(r, d))
        for f in fnames: set_file_perms(os.path.join(r, f))


# -----------------------------------------------------------
#  FS UTILS
# -----------------------------------------------------------
def norm(p: str) -> str:
    return (p or "").replace("\\", "/").strip()

def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)
    set_dir_perms(p)

def _is_mac_metadata_path(rel: str) -> bool:
    rl = rel.replace("\\", "/")
    return "/__macosx/" in rl.lower() or rl.lower().startswith("__macosx/") or os.path.basename(rl).startswith("._")


def copy_file(src_file: str, dst_root: str, dst_rel: str, log: list) -> int:
    if os.path.basename(src_file).startswith("._"):
        return 0
    dst = os.path.join(dst_root, norm(dst_rel)) if dst_rel else os.path.join(dst_root, os.path.basename(src_file))
    ensure_dir(os.path.dirname(dst))
    shutil.copy2(src_file, dst)
    set_file_perms(dst)
    log.append(f"  [+ fichier] {src_file} -> {dst}")
    return 1


def copy_folder_contents(src_dir: str, dst_root: str, dst_rel: str, log: list) -> int:
    base = os.path.join(dst_root, norm(dst_rel)) if dst_rel else dst_root
    ensure_dir(base)
    copied = 0
    for r, subdirs, files in os.walk(src_dir):
        subdirs[:] = [d for d in subdirs if d != "__MACOSX" and not d.startswith("._")]
        rel_from_src = os.path.relpath(r, src_dir).replace("\\", "/")
        if _is_mac_metadata_path(rel_from_src):
            continue
        rel = "" if rel_from_src == "." else rel_from_src
        outdir = os.path.join(base, rel)
        ensure_dir(outdir)
        for f in files:
            if f.startswith("._") or f == ".DS_Store":
                continue
            s = os.path.join(r, f)
            d = os.path.join(outdir, f)
            ensure_dir(os.path.dirname(d))
            shutil.copy2(s, d)
            set_file_perms(d)
            copied += 1
            log.append(f"  [+ fichier] {s} -> {d}")
    log.append(f"  [+ dossier] {src_dir} -> {base} ({copied} fichier(s))")
    return copied


# -----------------------------------------------------------
#  SUBPROCESS
# -----------------------------------------------------------
def _run(cmd: list):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(f"Echec: {' '.join(cmd)}\n{p.stderr.decode(errors='ignore')}")

def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


# -----------------------------------------------------------
#  EXTRACTION
# -----------------------------------------------------------
try:
    import py7zr
    HAS_7Z = True
except Exception:
    HAS_7Z = False

try:
    import rarfile
    HAS_RAR = True
except Exception:
    HAS_RAR = False


def extraire_archive(archive: str, out_dir: str):
    a = archive.lower()

    # ZIP
    if a.endswith(".zip"):
        if _have("7z"):
            _run(["7z", "x", "-y", f"-o{out_dir}", archive]); return
        try:
            with zipfile.ZipFile(archive, "r") as z:
                z.extractall(out_dir); return
        except Exception:
            if _have("unar"):
                _run(["unar", "-o", out_dir, "-f", archive]); return
            shutil.unpack_archive(archive, out_dir); return

    # 7Z
    if a.endswith(".7z"):
        if _have("7z"):
            _run(["7z", "x", "-y", f"-o{out_dir}", archive]); return
        if HAS_7Z:
            with py7zr.SevenZipFile(archive, "r") as z: z.extractall(out_dir); return
        raise RuntimeError("7z non disponible.")

    # RAR
    if a.endswith(".rar"):
        if _have("unar"):
            _run(["unar", "-o", out_dir, "-f", archive]); return
        if _have("7z"):
            _run(["7z", "x", "-y", f"-o{out_dir}", archive]); return
        if HAS_RAR:
            with rarfile.RarFile(archive) as rf: rf.extractall(out_dir); return
        raise RuntimeError("RAR non supporté.")

    # fallback
    shutil.unpack_archive(archive, out_dir)


# -----------------------------------------------------------
#  INDEX
# -----------------------------------------------------------
def indexer(base_dir: str):
    files, dirs = {}, {"": base_dir}
    for root, subdirs, filenames in os.walk(base_dir):
        subdirs[:] = [d for d in subdirs if d != "__MACOSX" and not d.startswith("._")]
        rel_root = os.path.relpath(root, base_dir).replace("\\", "/")
        if rel_root == ".": rel_root = ""
        if _is_mac_metadata_path(rel_root): continue
        dirs[rel_root.lower()] = root

        for d in subdirs:
            rel_d = os.path.join(rel_root, d).replace("\\", "/")
            if not _is_mac_metadata_path(rel_d):
                dirs[rel_d.lower()] = os.path.join(root, d)

        for f in filenames:
            if f.startswith("._") or f == ".DS_Store": continue
            absf = os.path.join(root, f)
            relf = os.path.relpath(absf, base_dir).replace("\\", "/")
            if not _is_mac_metadata_path(relf):
                files[relf.lower()] = absf

    return files, dirs


# -----------------------------------------------------------
#  FIND FILE / FOLDER
# -----------------------------------------------------------
def strip_num_prefix(name: str) -> str:
    n = os.path.basename(name).lower()
    return re.sub(r"^\d+\s*[_-]*\s*", "", n)

def _prefer_non_macosx(cands):
    good = [(rel,p) for rel,p in cands if "__macosx" not in rel.lower()]
    return good if good else list(cands)


def trouver_fichier(file_index: dict, src: str):
    key = norm(src).lower()
    if not key: return None

    if key in file_index and "__macosx" not in key:
        return file_index[key]

    cands = [(rel,p) for rel,p in file_index.items() if rel.endswith(key)]
    cands = _prefer_non_macosx(cands)
    if cands: return sorted(cands, key=lambda t: len(t[0]))[0][1]

    base = os.path.basename(key)
    if base:
        c2 = []
        for rel, abspath in file_index.items():
            if rel.endswith("/"+base) or rel == base or base in rel:
                c2.append((rel,abspath))
        c2 = _prefer_non_macosx(c2)
        if c2: return sorted(c2, key=lambda t: len(t[0]))[0][1]

    return None


def trouver_dossier(dir_index: dict, src: str):
    key = norm(src).lower()
    if key in dir_index and "__macosx" not in key:
        return dir_index[key]

    cands = [(rel,p) for rel,p in dir_index.items() if rel.endswith(key)]
    cands = _prefer_non_macosx(cands)
    if cands: return sorted(cands, key=lambda t: len(t[0]))[0][1]

    key_bn = strip_num_prefix(key)
    c2 = [(rel,p) for rel,p in dir_index.items() if strip_num_prefix(rel) == key_bn]
    c2 = _prefer_non_macosx(c2)
    if c2: return sorted(c2, key=lambda t: len(t[0]))[0][1]

    base = os.path.basename(key)
    if base:
        bn = strip_num_prefix(base)
        c3 = [(rel,p)for rel,p in dir_index.items() if strip_num_prefix(rel).endswith(bn)]
        c3 = _prefer_non_macosx(c3)
        if c3: return sorted(c3, key=lambda t: len(t[0]))[0][1]

    return None
# -----------------------------------------------------------
#  FOMOD HELPERS
# -----------------------------------------------------------
def _localname(e):
    return etree.QName(e).localname if isinstance(e,str) else etree.QName(e.tag).localname

def _find_case_insensitive_child_dir(parent: str, name_ci: str):
    try:
        for entry in os.listdir(parent):
            if os.path.isdir(os.path.join(parent, entry)) and entry.lower() == name_ci.lower():
                return os.path.join(parent, entry)
    except Exception:
        pass
    return None

def _find_moduleconfig_anywhere(root_dir: str):
    for r,_,files in os.walk(root_dir):
        for f in files:
            if f.lower() == "moduleconfig.xml":
                return os.path.join(r,f)
    return None

def lire_module_config(root):
    fomod = _find_case_insensitive_child_dir(root,"fomod")
    if fomod:
        mc = os.path.join(fomod,"ModuleConfig.xml")
        if os.path.isfile(mc):
            return etree.parse(mc).getroot()
    mc = _find_moduleconfig_anywhere(root)
    if mc:
        return etree.parse(mc).getroot()
    raise FileNotFoundError("ModuleConfig.xml introuvable")


def title_for(elem, default):
    a = elem.get("name")
    if a and a.strip(): return a.strip()
    b = elem.findtext("./name")
    if b and b.strip(): return b.strip()
    return default


def get_groups(step):
    out=[]
    for e in step.iter():
        if _localname(e) in ("optionalFileGroup","group"):
            out.append(e)
    return out

def get_options(group):
    ops=[]
    for e in group:
        if _localname(e) in ("plugin","option"):
            ops.append(e)
    if not ops:
        for e in group.iter():
            if _localname(e) in ("plugin","option"):
                ops.append(e)
    return ops

def get_group_type(group):
    return group.get("type","SelectExactlyOne")


def opt_name(opt):
    cand=[opt.get("name")]
    for xp in ("./name","./text",".//name",".//text"):
        try:
            v=opt.findtext(xp)
            if v and v.strip(): cand.append(v.strip())
        except: pass

    for v in cand:
        if v and v.strip(): return " ".join(v.split())

    node=opt.find(".//file") or opt.find(".//folder")
    if node is not None:
        src=node.get("source") or ""
        base=os.path.basename(norm(src))
        if base: return base
    return "Option"


def opt_desc(opt):
    for e in opt.iter():
        if _localname(e)=="description":
            return (e.text or "").strip()
    return ""


def opt_img(opt):
    for e in opt.iter():
        if _localname(e)=="image":
            p=(e.get("path") or e.get("src") or (e.text or "")).strip()
            if p: return p
    return None


# -----------------------------------------------------------
#  LABEL ÉTAPES
# -----------------------------------------------------------
_GENERIC={"option","options","groupe","group","general","misc","various",
          "default","step","étape","etape","choose","selection","select",
          "unp","cbbe","bodytype","type"}

def is_generic_label(s):
    if not s: return True
    t=" ".join(s.lower().split())
    if t in _GENERIC: return True
    if t.startswith("step ") or t.startswith("étape "): return True
    if len(t)<=3: return True
    return False

def humanize_token(tok):
    t=tok.replace("_"," ").replace("-"," ").replace("."," ").strip()
    return " ".join(t.split()).title()

def iter_step_sources(step):
    for g in get_groups(step):
        for o in get_options(g):
            for n in o.findall(".//file")+o.findall(".//folder"):
                src=(n.get("source") or "").strip()
                if src: yield src

def most_common_domain(step):
    c=Counter()
    for src in iter_step_sources(step):
        s=norm(src)
        top=s.split("/",1)[0] if "/" in s else s
        if top.strip(): c[top]+=1
    if not c: return None
    tok,_=c.most_common(1)[0]
    return humanize_token(tok)

def first_option_name_in_step(step):
    groups=get_groups(step)
    if not groups: return None
    opts=get_options(groups[0])
    if not opts: return None
    return opt_name(opts[0])

def derive_step_label(step, fallback):
    n=step.get("name") or step.findtext("./name")
    if n and not is_generic_label(n): return " ".join(n.split())

    for g in get_groups(step):
        gn=title_for(g,"")
        if gn and not is_generic_label(gn):
            return " ".join(gn.split())

    dom=most_common_domain(step)
    fopt=first_option_name_in_step(step) or ""
    if dom and not is_generic_label(dom):
        if fopt: return f"{dom} • {fopt}"
        return dom
    if fopt: return fopt

    return fallback


# -----------------------------------------------------------
#  DEDUPE STEPS
# -----------------------------------------------------------
def step_signature(step):
    sig=[]
    for g in get_groups(step):
        for o in get_options(g):
            name=opt_name(o)
            srcs=[]
            for n in o.findall(".//file")+o.findall(".//folder"):
                s=norm(n.get("source") or "")
                if s: srcs.append(s)
            sig.append((name,tuple(sorted(set(srcs)))))
    return tuple(sorted(sig))

def dedupe_steps(steps):
    seen=set(); out=[]
    for s in steps:
        sig=step_signature(s)
        if sig in seen: continue
        seen.add(sig); out.append(s)
    return out


# -----------------------------------------------------------
#  PRE-SELECTION (strict fileDependency only)
# -----------------------------------------------------------
def gather_option_dependencies_nodes(opt):
    nodes=[]
    nodes+=opt.findall(".//dependencies")
    nodes+=opt.findall(".//visible//dependencies")
    nodes+=opt.findall(".//typeDescriptor//dependencyType//patterns//pattern//dependencies")
    uniq=[]; seen=set()
    for n in nodes:
        if id(n) not in seen:
            uniq.append(n); seen.add(id(n))
    return uniq

def _eval_deps_preselect(dep_node, installed_basenames):
    if dep_node is None: return True
    op=(dep_node.get("operator") or "And").lower()
    results=[]
    for child in dep_node:
        tag=etree.QName(child.tag).localname
        if tag=="fileDependency":
            f=(child.get("file") or "").lower().strip()
            base=os.path.basename(f)
            state=(child.get("state") or "Active").lower()
            present= base in installed_basenames
            res=(state=="active" and present) or (state=="inactive" and not present)
            results.append(res)
        elif tag=="dependencies":
            results.append(_eval_deps_preselect(child, installed_basenames))
        else:
            results.append(True)
    if not results: return True
    if op=="and": return all(results)
    if op=="or": return any(results)
    if op=="not": return not all(results)
    return all(results)

def option_should_autoselect(opt, installed_basenames):
    deps=gather_option_dependencies_nodes(opt)
    if not deps: return False
    for d in deps:
        if _eval_deps_preselect(d, installed_basenames):
            return True
    return False


# -----------------------------------------------------------
#  info.xml
# -----------------------------------------------------------
def find_info_xml_anywhere(base_dir):
    for r,_,files in os.walk(base_dir):
        for f in files:
            if f.lower()=="info.xml":
                return os.path.join(r,f)
    return None

def parse_info_xml(path):
    try:
        tree=etree.parse(path)
        root=tree.getroot()
    except Exception:
        return {"Nom":"","Auteur":"","Version":"","Site":"", "Description": f"(Impossible de lire {os.path.basename(path)})"}

    def _first(cands):
        for el in root.iter():
            ln=etree.QName(el).localname.lower()
            if ln in cands:
                t="".join(el.itertext()).strip()
                if t: return t
        return ""

    def _all(cands):
        out=[]
        for el in root.iter():
            ln=etree.QName(el).localname.lower()
            if ln in cands:
                t="".join(el.itertext()).strip()
                if t: out.append(t)
        return "\n\n".join(out) if out else ""

    return {
        "Nom":_first({"name","modname","title"}),
        "Auteur":_first({"author","authors"}),
        "Version":_first({"version"}),
        "Site":_first({"website","url","homepage","link"}),
        "Description":_all({"description","summary","details"}) or "(Aucune description)"
    }


# -----------------------------------------------------------
#  DATA SCAN (cached)
# -----------------------------------------------------------
SCAN_EXTS={".esp",".esm",".esl",".bsa",".ba2",".dll"}

def _dir_quick_signature(path):
    try: m=os.stat(path).st_mtime
    except: m=0
    count=0
    for r,sub,files in os.walk(path):
        sub[:]=[d for d in sub if d!="__MACOSX" and not d.startswith("._")]
        count+=len(files)
    return (m,count)

def scan_data_dir(path):
    out=set()
    if not path or not os.path.isdir(path): return out
    for r,sub,files in os.walk(path):
        sub[:]=[d for d in sub if d!="__MACOSX" and not d.startswith("._")]
        for f in files:
            if f.startswith("._") or f==".DS_Store": continue
            ext=os.path.splitext(f)[1].lower()
            if ext in SCAN_EXTS:
                out.add(f.lower())
    return out


# -----------------------------------------------------------
#  REQUIRED & CONDITIONAL (STUB)
# -----------------------------------------------------------
# Cette fonction n'est pas complètement implémentée, mais est conservée
# pour maintenir la structure du simulateur.
def apply_required_and_conditional(root_xml, active_flags, file_index, dir_index, installed_basenames, staging, log):
    # Logique complexe de RequiredInstallFiles/ConditionalFileInstalls ignorée ici
    log.append("\n[STUB] Application des RequiredInstallFiles/ConditionalFileInstalls ignorée.")
    return 0, 0 # copied, missing


# -----------------------------------------------------------
#  GUI
# -----------------------------------------------------------
class App:
    URL_RE=re.compile(r"(https?://[^\s)]+|www\.[^\s)]+)",re.IGNORECASE)

    def __init__(self, root):
        self.root=root
        self.root.title("Simulateur FOMOD (générique)")
        # Hauteur réduite à 780px
        self.root.geometry("1280x780") 
        self.root.configure(bg="#1e1e1e")

        # état
        self.temp=None
        self.root_xml=None
        self.file_index={}
        self.dir_index={}
        self.steps=[]
        self.state={}
        self.preview_path=None
        self.current_step_idx=0
        self.installed_basenames=set()
        self.data_dir_path=None
        self._scan_cache={}
        self.translate_enabled=False

        # Police
        self.UI_FONT=("Arial",14)
        self.UI_FONT_B=("Arial",14,"bold")
        for nm in ("TkDefaultFont","TkTextFont","TkHeadingFont","TkMenuFont",
                   "TkCaptionFont","TkTooltipFont","TkFixedFont","TkIconFont"):
            try: tkfont.nametofont(nm).configure(family="Arial",size=14)
            except: pass

        # Staging
        self.staging_parent=os.path.join(os.path.expanduser("~"),"Desktop")
        self.staging_name_var=tk.StringVar(value="Staging")
        self.staging_dir=os.path.join(self.staging_parent,self.staging_name_var.get())
        ensure_dir(self.staging_dir)

        # Styles flat
        self.style=ttk.Style(root)
        try: self.style.theme_use("clam")
        except: pass

        base="#1e1e1e"; pane="#222"; side="#262626"

        self.style.configure(".", background=base, foreground="#ddd", font=self.UI_FONT)
        self.style.configure("TFrame", background=base)
        self.style.configure("Title.TLabel", background=base, foreground="#fff", font=self.UI_FONT_B)

        # boutons flat + centrés + hauteur uniforme
        btn_height = 38

        def fix_button_style(name, bg, fg="#fff"):
            self.style.configure(name,
                background=bg, foreground=fg,
                padding=(10,10), anchor="center",
                relief="flat", font=self.UI_FONT)
            self.style.map(name,
                background=[("active", bg), ("pressed", bg)],
                relief=[("pressed","flat"),("active","flat")])

        fix_button_style("Sidebar.TButton", "#333")
        fix_button_style("Sidebar.Center.TButton", "#444")
        fix_button_style("Sidebar.Action.TButton", "#0ea5e9")
        fix_button_style("Vortex.Main.TButton", "#fbbf24", "#1a1a1a")

        self.style.configure("Card.TLabelframe", background=pane, relief="flat")
        self.style.configure("Card.TLabelframe.Label", background=pane, foreground="#ddd", font=self.UI_FONT_B)
        
        # Style Scrollbar Flat (pour ttk) - Correction pour éliminer les bords et le contour
        self.style.configure("Vertical.TScrollbar", 
                             background="#333", 
                             troughcolor="#222", 
                             arrowcolor="#ddd", 
                             bordercolor="#222", 
                             relief="flat",
                             borderwidth=0)
        self.style.map("Vertical.TScrollbar", 
                       background=[("active", "#444"), ("pressed", "#555")])
        
        # S'assurer que le TButton de l'ascenseur est aussi plat
        self.style.configure("TScrollbar", borderwidth=0, relief="flat") 
        
        self.style.configure("Vortex.MainBold.TButton",
                     background="#fbbf24",
                     foreground="#1a1a1a",
                     padding=(10, 8),
                     relief="flat",
                     font=("Arial", 14, "bold"))
        self.style.map("Vortex.MainBold.TButton",
               background=[("active", "#f59e0b"), ("pressed", "#d97706")],
               foreground=[("disabled", "#666")])

        # Conteneur principal avec marges globales
        self.main_container = ttk.Frame(root, style="TFrame", padding=(12, 12, 12, 12))
        self.main_container.pack(fill="both", expand=True)

        # 3 colonnes (Panedwindow à l'intérieur du conteneur avec marge)
        self.panes=ttk.Panedwindow(self.main_container, orient="horizontal")
        self.panes.pack(fill="both", expand=True)

        self.left=ttk.Frame(self.panes, style="Sidebar.TFrame")
        self.center=ttk.Frame(self.panes, style="Pane.TFrame")
        self.right=ttk.Frame(self.panes, style="Pane.TFrame")

        # APPLICATION DES POIDS DEMANDÉS : 20 (Gauche) / 30 (Centre) / 50 (Droite)
        self.panes.add(self.left, weight=20)
        self.panes.add(self.center, weight=30) 
        self.panes.add(self.right, weight=50)  
        
        # Correction : Forcer la position initiale des sashes pour garantir les poids (20% et 50%)
        def initial_sash_pos():
            self.root.update_idletasks()
            panes_width = self.panes.winfo_width()
            
            if panes_width < 100: 
                 panes_width = 1280 - 24 # Largeur par défaut - padding
            
            sash0_pos = int(panes_width * 0.20)
            sash1_pos = int(panes_width * 0.50)
            
            try:
                self.panes.sashpos(0, sash0_pos) 
                self.panes.sashpos(1, sash1_pos)
            except Exception:
                pass 
        
        self.root.after(100, initial_sash_pos) 

        # ---------- COLONNE GAUCHE ----------
        
        # Header (Haut)
        self.left_header=ttk.Frame(self.left, style="Sidebar.TFrame")
        self.left_header.pack(side="top", fill="x", padx=8, pady=(8,6))

        self.open_btn = ttk.Button(self.left_header, text="📦 Ouvrir un mod FOMOD",
                                   style="Vortex.MainBold.TButton", command=self.ouvrir_archive)
        self.open_btn.pack(fill="x", ipady=6)

        self.translate_btn = ttk.Button(self.left_header,
                                        text="TRADUCTION : OFF",
                                        style="Sidebar.Center.TButton",
                                        command=self.toggle_translation)
        self.translate_btn.pack(fill="x", pady=(8,0), ipady=6)

        self.info_btn=ttk.Button(self.left_header, text="ℹ️ Infos du mod",
                                 style="Sidebar.Center.TButton",
                                 command=self.afficher_info_mod)
        self.info_btn.pack(fill="x", pady=(8,0), ipady=6)

        # DATA (Milieu)
        self.left_data=ttk.Frame(self.left, style="Sidebar.TFrame")
        self.left_data.pack(side="top", fill="x", padx=8, pady=(6,0))

        self.data_btn = ttk.Button(self.left_data, text="📂 Choisir dossier Data",
                                   style="Sidebar.TButton",
                                   command=self.choisir_data_dir)
        self.data_btn.pack(fill="x", ipady=6)

        self.data_label=tk.Label(self.left_data, text="Data : (non défini)",
                                 bg="#262626", fg="#bbb", wraplength=240,
                                 justify="center", font=self.UI_FONT)
        self.data_label.pack(fill="x", pady=(4,0))

        # ACTIONS (Bas)
        self.left_actions=ttk.Frame(self.left, style="Sidebar.TFrame")
        self.left_actions.pack(side="bottom", fill="x", padx=8, pady=8)

        ttk.Label(self.left_actions, text="Nom du dossier :", background="#262626",
                  foreground="#ddd", font=self.UI_FONT).pack(anchor="center", pady=(0,2))

        name_entry=ttk.Entry(self.left_actions, textvariable=self.staging_name_var)
        name_entry.pack(fill="x", pady=(0,6))
        name_entry.bind("<Return>", self.apply_name)
        name_entry.bind("<FocusOut>", self.apply_name)

        self.parent_btn = ttk.Button(self.left_actions, text="📁 Changer dossier parent",
                                     style="Sidebar.TButton", command=self.choisir_parent)
        self.parent_btn.pack(fill="x", ipady=6)

        self.staging_label=tk.Label(self.left_actions, text=self.staging_dir,
                                    bg="#262626", fg="#bbb",
                                    wraplength=240, justify="center", font=self.UI_FONT)
        self.staging_label.pack(fill="x", pady=(4,8))
        
        # Le bouton Générer est dans un conteneur pour garantir l'alignement
        self.gen_btn_container = ttk.Frame(self.left_actions, style="Sidebar.TFrame")
        self.gen_btn_container.pack(fill="x", pady=(10, 0))

        self.gen_btn = ttk.Button(self.gen_btn_container, text="GÉNÉRER LE STAGING",
                                  style="Sidebar.Action.TButton",
                                  command=self.installer_selection)
        self.gen_btn.pack(fill="x", ipady=6)


        # ---------- COLONNE CENTRALE ----------
        # center_container prend tout l'espace vertical disponible au-dessus des boutons de navigation
        self.center_container=ttk.Frame(self.center, style="Pane.TFrame")
        self.center_container.pack(side="top", fill="both", expand=True, padx=12, pady=12)

        self.canvas=tk.Canvas(self.center_container, bg="#222", highlightthickness=0, bd=0)
        self.scroll_frame=ttk.Frame(self.canvas, style="Pane.TFrame")
        self.canvas_win=self.canvas.create_window((0,0), window=self.scroll_frame, anchor="nw")

        # Initialisation du Canvas pour prendre tout l'espace initialement
        self.canvas.pack(side="top", fill="both", expand=True)

        # SCROLLBAR (Initialisation unique, masquage par pack_forget)
        self._scroll_visible=False
        self.scrollbar = ttk.Scrollbar(self.center_container, orient="vertical", command=self.canvas.yview, style="Vertical.TScrollbar")
        
        # On lie le scrollbar au Canvas une seule fois
        self.canvas.configure(yscrollcommand=self.scrollbar.set)


        self.canvas.bind("<Configure>", self._on_canvas_cfg)
        self.scroll_frame.bind("<Configure>", self._on_frame_cfg)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.scroll_frame.bind("<MouseWheel>", self._on_wheel)


        # NAVIGATION (RETOUR / CONTINUER)
        self.center_nav=ttk.Frame(self.center, style="Pane.TFrame")
        # Alignement en bas du center. pady=(0, 12) pour aligner verticalement avec les boutons de gauche
        self.center_nav.pack(side="bottom", fill="x", padx=12, pady=(0, 12)) 

        self.back_btn=ttk.Button(self.center_nav, text="RETOUR",
                                 style="Sidebar.TButton",
                                 command=self.prev_step)
        # fill="x", expand=True pour que les boutons s'élargissent horizontalement
        self.back_btn.pack(side="left", fill="x", expand=True, ipadx=10, ipady=6, padx=(0, 5)) 

        self.next_btn=ttk.Button(self.center_nav, text="CONTINUER",
                                 style="Sidebar.Action.TButton",
                                 command=self.next_step)
        # fill="x", expand=True pour que les boutons s'élargissent horizontalement
        self.next_btn.pack(side="right", fill="x", expand=True, ipadx=10, ipady=6, padx=(5, 0))


        # ---------- COLONNE DROITE ----------
        self.right_container=ttk.Frame(self.right, style="Pane.TFrame")
        self.right_container.pack(fill="both", expand=True, padx=12, pady=12)

        self.desc=tk.Message(self.right_container, text="Description",
                             bg="#222", fg="#ddd", width=560,
                             font=self.UI_FONT, justify="left")
        self.desc.pack(padx=6, pady=6)

        self.img_label=tk.Label(self.right_container, bg="#222", cursor="hand2")
        self.img_label.pack(padx=6, pady=6)
        self.img_label.bind("<Button-1>", self.apercu_full)

        # Centrage initial
        self._center()

    # -----------------------------------------------------------
    #  CENTRAGE / SCROLL FIX
    # -----------------------------------------------------------
    def _center(self):
        self.root.update_idletasks()
        w=self.root.winfo_width(); h=self.root.winfo_height()
        sw=self.root.winfo_screenwidth(); sh=self.root.winfo_screenheight()
        x=(sw-w)//2; y=(sh-h)//2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # Fonction pour centrer les fenêtres Toplevel
    def _center_toplevel(self, top: Toplevel):
        top.update_idletasks()
        w = top.winfo_width()
        h = top.winfo_height()
        sw = top.winfo_screenwidth()
        sh = top.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        # Définit la position sans changer la taille courante
        top.geometry(f"+{x}+{y}")

    def _on_canvas_cfg(self, e):
        # Assure que la fenêtre interne (scroll_frame) a la même largeur que le canvas
        self.canvas.itemconfig(self.canvas_win, width=e.width) 
        self._check_scrollbar_visibility() # Vérifie si la barre doit apparaître après redimensionnement

    def _on_frame_cfg(self):
        # Assure que la zone de défilement est mise à jour lorsque le contenu change de taille
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._check_scrollbar_visibility() # Vérifie si la barre doit apparaître après changement de contenu

    def _on_wheel(self, e):
        # Utilise yview_scroll pour défiler
        if e.delta: self.canvas.yview_scroll(-1 if e.delta>0 else 1,"units")

    def _check_scrollbar_visibility(self):
        # Logique pour vérifier et gérer l'affichage/masquage de l'ascenseur
        self.canvas.update_idletasks()
        bbox = self.canvas.bbox("all")
        if not bbox: return

        content_h = bbox[3] - bbox[1]
        visible_h = self.canvas.winfo_height()
        need_scrollbar = content_h > visible_h + 1
        
        # Masquer ou afficher la barre de défilement
        if need_scrollbar and not self._scroll_visible:
            # FIX HAUTEUR : On oublie le pack précédent du Canvas et on emballe les deux correctement
            self.canvas.pack_forget()
            
            # 1. On affiche l'ascenseur à droite (il prend toute la hauteur y)
            self.scrollbar.pack(side="right", fill="y")
            
            # 2. On affiche le Canvas à gauche, il prend la hauteur restante
            self.canvas.pack(side="left", fill="both", expand=True) 
            
            self._scroll_visible = True
        elif not need_scrollbar and self._scroll_visible:
            # Masque l'ascenseur
            self.scrollbar.pack_forget()
            
            # Re-pack le Canvas pour qu'il prenne toute la largeur/hauteur comme il le faisait initialement
            self.canvas.pack_forget()
            self.canvas.pack(side="top", fill="both", expand=True)
            
            self._scroll_visible = False


    # -----------------------------------------------------------
    #  TRANSLATION
    # -----------------------------------------------------------
    def toggle_translation(self):
        # Pas de vérification d'installation lourde nécessaire ici (dépendance en ligne)

        self.translate_enabled = not self.translate_enabled
        if self.translate_enabled:
            self.translate_btn.configure(text="TRADUCTION : ON")
        else:
            self.translate_btn.configure(text="TRADUCTION : OFF")

        if self.root_xml and self.steps:
            self.afficher_etape(self.steps[self.current_step_idx], self.current_step_idx)

    def _translate(self, text: str) -> str:
        if not self.translate_enabled:
            return text
        if not text.strip():
            return text
        # Rétablissement de la logique googletrans
        if not _HAS_TRANSLATOR:
            return text + "\n\n(Traduction indisponible)"
        try:
            t=_translator.translate(text, dest="fr")
            return t.text
        except Exception:
            # L'échec est souvent dû à un problème de connexion ou de limite de requête
            return text + "\n\n(Échec traduction : problème réseau ou service)"

    # -----------------------------------------------------------
    #  CHOIX STAGING
    # -----------------------------------------------------------
    def apply_name(self, *_):
        nm=self.staging_name_var.get().strip() or "Staging"
        self.staging_name_var.set(nm)
        self.staging_dir=os.path.join(self.staging_parent,nm)
        ensure_dir(self.staging_dir)
        self.staging_label.configure(text=self.staging_dir)

    def choisir_parent(self):
        p=filedialog.askdirectory(title="Choisir le dossier parent")
        if p:
            self.staging_parent=p
            self.apply_name()

    # -----------------------------------------------------------
    #  DATA DIR
    # -----------------------------------------------------------
    def _scan_cached(self, path):
        sig=_dir_quick_signature(path)
        c=self._scan_cache.get(path)
        if c and c[0]==sig:
            return set(c[1])
        found=scan_data_dir(path)
        self._scan_cache[path]=(sig,set(found))
        return set(found)

    def choisir_data_dir(self):
        p=filedialog.askdirectory(title="Choisir le dossier Data")
        if not p: return
        self.data_dir_path=p
        self.installed_basenames=self._scan_cached(p)
        self.state={}
        self.data_label.configure(text=f"Data : {p}\n({len(self.installed_basenames)} fichiers détectés)")
        if self.root_xml and self.steps:
            self.afficher_etape(self.steps[self.current_step_idx], self.current_step_idx)
            self._update_nav()

    # -----------------------------------------------------------
    #  OUVERTURE ARCHIVE
    # -----------------------------------------------------------
    def _reset(self):
        self.img_label.configure(image="")
        self.preview_path=None
        self.desc.configure(text="Description")
        if self.temp:
            try: self.temp.cleanup()
            except: pass
        self.temp=None
        self.root_xml=None
        self.file_index={}; self.dir_index={}
        self.steps=[]; self.state={}
        self.current_step_idx=0

    def ouvrir_archive(self):
        p=filedialog.askopenfilename(
            title="Choisir une archive",
            filetypes=[("Mods",".zip .7z .rar")]
        )
        if not p: return

        try:
            self._reset()
            self.temp=tempfile.TemporaryDirectory()
            extraire_archive(p, self.temp.name)

            self.root_xml=lire_module_config(self.temp.name)
            self.file_index, self.dir_index=indexer(self.temp.name)

            raw=list(self.root_xml.iterfind(".//installStep"))
            if not raw:
                raw=[e for e in self.root_xml.iter() if _localname(e)=="installStep"]

            self.steps=dedupe_steps(raw)
            self.state={}
            self.current_step_idx=0
            if self.steps:
                self.afficher_etape(self.steps[0],0)
            else:
                 messagebox.showerror("Erreur FOMOD", "Aucune étape d'installation ('installStep') trouvée.")
                 self.root_xml=None
            self._update_nav()

        except FileNotFoundError as fnfe:
             messagebox.showerror("Erreur", str(fnfe))
             self._reset()
        except RuntimeError as re:
             messagebox.showerror("Erreur d'extraction", str(re))
             self._reset()
        except Exception as e:
             messagebox.showerror("Erreur", f"Une erreur inattendue est survenue: {e}")
             self._reset()


    # -----------------------------------------------------------
    #  INFOS MOD
    # -----------------------------------------------------------
    def open_url(self,url):
        try:
            if url.lower().startswith("www."): url="http://"+url
            webbrowser.open(url)
        except: pass

    def _insert_links(self, tw: tk.Text, content):
        tw.configure(state="normal")
        pos=0
        for m in self.URL_RE.finditer(content or ""):
            start,end=m.span()
            url=m.group(0)
            tw.insert("end", content[pos:start])
            tag=f"link_{start}_{end}"
            tw.insert("end", url, (tag,))
            tw.tag_configure(tag, foreground="#60a5fa", underline=True)
            tw.tag_bind(tag, "<Button-1>", lambda e,u=url: self.open_url(u))
            pos=end
        tw.insert("end", content[pos:])
        tw.configure(state="disabled")

    def afficher_info_mod(self):
        if not self.temp:
            messagebox.showwarning("Info","Ouvrez un mod.")
            return
        path=find_info_xml_anywhere(self.temp.name)
        if not path:
            messagebox.showinfo("Infos","info.xml introuvable.")
            return

        meta=parse_info_xml(path)

        # traduction si ON
        if self.translate_enabled:
            for k in ("Nom","Auteur","Version","Site","Description"):
                meta[k]=self._translate(meta[k])

        top=Toplevel(self.root)
        top.title("Infos du mod")
        top.configure(bg="#1e1e1e")

        frm=ttk.Frame(top, style="Pane.TFrame")
        frm.pack(fill="both", expand=True, padx=16, pady=16)

        def row(lbl, val, r):
            ttk.Label(frm,text=lbl,style="Title.TLabel").grid(row=r,column=0,sticky="nw",padx=(0,10))
            ent=tk.Label(frm,text=val or "—", bg="#222", fg="#ddd",
                         anchor="w", justify="left", wraplength=720,
                         font=self.UI_FONT)
            ent.grid(row=r,column=1,sticky="new")
            frm.grid_columnconfigure(1, weight=1)

        row("Nom", meta.get("Nom",""), 0)
        row("Auteur", meta.get("Auteur",""),1)
        row("Version", meta.get("Version",""),2)

        ttk.Label(frm, text="Site", style="Title.TLabel").grid(row=3,column=0,sticky="nw",padx=(0,10))

        sf=ttk.Frame(frm, style="Pane.TFrame")
        sf.grid(row=3,column=1,sticky="new")

        t=tk.Text(sf, wrap="word", bg="#222", fg="#ddd", relief="flat",
                  highlightthickness=0, font=self.UI_FONT, height=2)
        t.pack(fill="x", expand=True)
        self._insert_links(t, meta.get("Site","") or "—")

        # description
        ttk.Label(frm,text="Description",style="Title.TLabel").grid(row=4,column=0,sticky="nw",padx=(0,10))

        df=ttk.Frame(frm, style="Pane.TFrame")
        df.grid(row=4,column=1,sticky="nsew")
        frm.grid_rowconfigure(4,weight=1)

        td=tk.Text(df, wrap="word", bg="#222", fg="#ddd", relief="flat",
                   highlightthickness=0, font=self.UI_FONT)
        vs=ttk.Scrollbar(df, orient="vertical", command=td.yview)
        td.configure(yscrollcommand=vs.set)
        td.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        td.insert("end", meta.get("Description",""))
        td.configure(state="disabled")

        ttk.Button(frm,text="Fermer",style="Sidebar.TButton",
                   command=top.destroy).grid(row=5,column=1,sticky="e",pady=(10,0))
        
        # Centrage de la fenêtre d'infos
        self._center_toplevel(top)


    # -----------------------------------------------------------
    #  AFFICHAGE ÉTAPE
    # -----------------------------------------------------------
    def _norm(self,s): return (" ".join((s or "").split())).lower()

    def afficher_etape(self, step, idx):
        for w in self.scroll_frame.winfo_children(): w.destroy()

        step_title=derive_step_label(step,f"Étape {idx+1}")
        groups=get_groups(step)

        same = any(self._norm(title_for(g,"")) == self._norm(step_title) for g in groups)
        if not same:
            ttk.Label(self.scroll_frame, text=step_title,
                      style="Title.TLabel").pack(anchor="w", padx=6, pady=6)

        for gidx,g in enumerate(groups):
            gname=title_for(g,f"Groupe {gidx+1}")
            gtype=get_group_type(g)
            opts=get_options(g)

            lf=ttk.Labelframe(self.scroll_frame, text=gname, style="Card.TLabelframe")
            lf.pack(fill="x", padx=6, pady=8)

            key=(idx,gidx)
            existing=self.state.get(key)

            # SINGLE
            if gtype=="SelectExactlyOne":
                if existing is None:
                    var=tk.StringVar(value="__none__")
                    matches=[o for o in opts if option_should_autoselect(o,self.installed_basenames)]
                    if len(matches)==1:
                        var.set(opt_name(matches[0]))
                    self.state[key]={"type":"single","var":var,"opts":opts}
                else:
                    var=existing["var"]
                    self.state[key]["opts"]=opts
                    names=[opt_name(o) for o in opts]
                    if var.get() not in names:
                        sel="__none__"
                        matches=[o for o in opts if option_should_autoselect(o,self.installed_basenames)]
                        if len(matches)==1: sel=opt_name(matches[0])
                        var.set(sel)

                for opt in opts:
                    name=opt_name(opt)
                    desc=opt_desc(opt)
                    if self.translate_enabled:
                        desc=self._translate(desc)
                    imgp=opt_img(opt)

                    # tk.Radiobutton (aspect visuel préféré)
                    rb=tk.Radiobutton(
                        lf, text=name,
                        variable=var, value=name,
                        bg="#222", fg="#eee",
                        selectcolor="#222",
                        activebackground="#222",
                        relief="flat",
                        highlightthickness=0,
                        anchor="w", justify="left",
                        indicatoron=1,
                        font=self.UI_FONT
                    )
                    rb.pack(anchor="w", padx=10, pady=2)
                    if var.get()=="__none__": rb.deselect()
                    rb.bind("<Enter>", lambda e,o=opt,d=desc,p=imgp: self.maj_apercu(o,d,p))

            # MULTI
            else:
                if existing is None:
                    pairs=[]
                    for opt in opts:
                        default=option_should_autoselect(opt,self.installed_basenames)
                        pairs.append((opt, tk.BooleanVar(value=default)))
                    self.state[key]={"type":"multi","vars":pairs}
                else:
                    old={opt_name(o):v for o,v in existing["vars"]}
                    pairs=[]
                    for opt in opts:
                        nm=opt_name(opt)
                        if nm in old:
                            pairs.append((opt, old[nm]))
                        else:
                            pairs.append((opt, tk.BooleanVar(
                                value=option_should_autoselect(opt,self.installed_basenames))))
                    self.state[key]["vars"]=pairs

                for opt,v in self.state[key]["vars"]:
                    name=opt_name(opt)
                    desc=opt_desc(opt)
                    if self.translate_enabled:
                        desc=self._translate(desc)
                    imgp=opt_img(opt)

                    # tk.Checkbutton (aspect visuel préféré)
                    cb=tk.Checkbutton(
                        lf, text=name, variable=v,
                        bg="#222", fg="#eee",
                        selectcolor="#222",
                        activebackground="#222",
                        relief="flat",
                        highlightthickness=0,
                        anchor="w", justify="left",
                        font=self.UI_FONT
                    )
                    cb.pack(anchor="w", padx=10, pady=2)
                    cb.bind("<Enter>", lambda e,o=opt,d=desc,p=imgp: self.maj_apercu(o,d,p))

        self._update_nav()
        self._check_scrollbar_visibility() # Appel de la fonction de vérification


    # -----------------------------------------------------------
    #  NAVIGATION
    # -----------------------------------------------------------
    def _update_nav(self):
        if not self.steps:
            self.back_btn.state(["disabled"])
            self.next_btn.state(["disabled"])
            return

        first = (self.current_step_idx<=0)
        last = (self.current_step_idx>=len(self.steps)-1)

        self.back_btn.state(["disabled" if first else "!disabled"])
        self.next_btn.state(["disabled" if last else "!disabled"])

    def next_step(self):
        if self.current_step_idx < len(self.steps)-1:
            self.current_step_idx+=1
            self.afficher_etape(self.steps[self.current_step_idx], self.current_step_idx)

    def prev_step(self):
        if self.current_step_idx>0:
            self.current_step_idx-=1
            self.afficher_etape(self.steps[self.current_step_idx], self.current_step_idx)

    # -----------------------------------------------------------
    #  APERÇUS
    # -----------------------------------------------------------
    def maj_apercu(self, _opt, desc, img_rel):
        self.desc.configure(text=desc or "(aucune description)")
        self.preview_path=None
        full=None

        if img_rel:
            cand=os.path.join(self.temp.name, norm(img_rel))
            if os.path.isfile(cand):
                full=cand
            else:
                full=trouver_fichier(self.file_index,img_rel)

        if full and os.path.isfile(full):
            try:
                im=Image.open(full)
                im.thumbnail((640,640))
                tki=ImageTk.PhotoImage(im)
                self.img_label.configure(image=tki)
                self.img_label.image=tki
                self.preview_path=full
                return
            except Exception:
                pass

        self.img_label.configure(image="")
        self.img_label.image=None

    def apercu_full(self, e):
        if not self.preview_path or not os.path.isfile(self.preview_path):
            return
        im=Image.open(self.preview_path)
        w,h=im.size

        top=Toplevel(self.root)
        top.title("Aperçu taille réelle")

        sw,sh=self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        win_w,win_h=min(w,sw-40),min(h,sh-80)
        top.geometry(f"{win_w}x{win_h}") # Définit la taille

        canv=tk.Canvas(top,bg="#1e1e1e",highlightthickness=0,bd=0,
                       scrollregion=(0,0,w,h))
        canv.pack(fill="both",expand=True)

        if w>win_w or h>win_h:
            vs=ttk.Scrollbar(top,orient="vertical",command=canv.yview)
            hs=ttk.Scrollbar(top,orient="horizontal",command=canv.xview)
            canv.configure(yscrollcommand=vs.set,xscrollcommand=hs.set)
            vs.pack(side="right",fill="y")
            hs.pack(side="bottom",fill="x")

        tki=ImageTk.PhotoImage(im)
        canv.create_image(0,0,anchor="nw",image=tki)
        canv.image=tki

        # Centrage de la fenêtre de preview
        self._center_toplevel(top)


    # -----------------------------------------------------------
    #  STAGING (INSTALLATION)
    # -----------------------------------------------------------
    def collect_selected(self):
        sel=[]
        for _,info in self.state.items():
            if info["type"]=="single":
                v=info["var"].get()
                if v and v!="__none__":
                    opt=next((o for o in info["opts"] if opt_name(o)==v),None)
                    if opt: sel.append(opt)
            else:
                for o,v in info["vars"]:
                    if v.get(): sel.append(o)
        return sel

    def installer_selection(self):
        selected=self.collect_selected()
        if not selected:
            messagebox.showwarning("Avertissement","Aucune option sélectionnée.")
            return

        staging=self.staging_dir
        ensure_dir(staging)
        log=[]
        copied=missing=0

        for opt in selected:
            log.append(f"\n[{opt_name(opt)}]")
            nodes=opt.findall(".//file")+opt.findall(".//folder")
            for node in nodes:
                tag=_localname(node).lower()
                src=norm(node.get("source") or "")
                dst=norm(node.get("destination") or "")

                src_file=trouver_fichier(self.file_index,src)
                src_dir=trouver_dossier(self.dir_index,src)

                try:
                    if tag=="file":
                        # Logique: Si c'est une balise <file>
                        if src_file:
                             copied+=copy_file(src_file,staging,dst,log)
                        # Fallback: Si la source est un dossier (erreur de FOMOD)
                        elif src_dir:
                            copied+=copy_folder_contents(src_dir,staging,dst,log)
                        else:
                            log.append(f"  [manquant] (fichier) {src}")
                            missing+=1
                    else: # tag=="folder"
                        # Logique: Si c'est une balise <folder>
                        if src_dir:
                            copied+=copy_folder_contents(src_dir,staging,dst,log)
                        # Fallback: Si la source est un fichier (erreur de FOMOD)
                        elif src_file:
                            copied+=copy_file(src_file,staging,dst,log)
                        else:
                            log.append(f"  [manquant] (dossier) {src}")
                            missing+=1
                except Exception as ex:
                    log.append(f"  [erreur] {src} -> {dst} : {ex}")


        # required/conditional
        active_flags = {}
        for opt in selected:
            pass  # flags non utilisés en préselection strict fileDependency

        try:
            c2,m2 = apply_required_and_conditional(
                self.root_xml, active_flags,
                self.file_index, self.dir_index,
                self.installed_basenames, staging, log
            )
            copied+=c2; missing+=m2
        except Exception as ex:
            log.append(f"[conditional error] {ex}")

        set_tree_perms(staging)
        resume=f"\n--- Résumé ---\n{copied} fichier(s) copié(s), {missing} manquant(s)"
        log.append(resume)

        try:
            with open(os.path.join(staging,"install_log.txt"),"w",encoding="utf-8") as f:
                f.write("\n".join(log))
        except: pass

        try: 
            if os.name == 'nt':
                 subprocess.Popen(['explorer', staging])
            elif os.uname().sysname == 'Darwin':
                subprocess.Popen(['open', staging])
            else:
                 subprocess.Popen(['xdg-open', staging])
        except Exception:
            pass # Ne pas crasher si l'ouverture échoue

        messagebox.showinfo("OK", f"Staging généré :\n{staging}\n{resume}")


# -----------------------------------------------------------
#  MAIN
# -----------------------------------------------------------
if __name__=="__main__":
    root=tk.Tk()
    app=App(root)
    root.mainloop()