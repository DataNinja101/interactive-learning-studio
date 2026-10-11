#!/usr/bin/env python3
"""Extract page-marked text from course materials so questions can cite page/slide numbers.

Usage:
  extract_sources.py FILE_OR_DIR [...] -o sources/

Writes, per source, sources/<id>.txt with "=== page N ===" (or slide/sheet) markers,
and sources/sources.json: a manifest listing id, title, file, unit type, unit count,
character count and pages that came back (nearly) empty — usually scanned images that
need OCR. Also prints a ready-to-paste "sources" array for the course JSON.

Supports .pdf .docx .pptx .xlsx .txt .md .html/.htm. Uses pdfplumber / pypdf /
python-docx / python-pptx / openpyxl when installed and falls back to pdftotext or the
standard library otherwise.
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

SUPPORTED = {".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".md", ".markdown", ".html", ".htm"}
LOW_TEXT = 40  # characters; below this a page is probably an image


def clean(s):
    s = s.replace("­", "").replace("\r", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# ---------- PDF ----------
def pdf_pages(path):
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return [clean(p.extract_text() or "") for p in pdf.pages], "pdfplumber"
    except ImportError:
        pass
    except Exception as e:
        print(f"  pdfplumber failed ({e}); trying another reader", file=sys.stderr)
    try:
        from pypdf import PdfReader
        return [clean(p.extract_text() or "") for p in PdfReader(path).pages], "pypdf"
    except ImportError:
        pass
    except Exception as e:
        print(f"  pypdf failed ({e}); trying pdftotext", file=sys.stderr)
    if shutil.which("pdftotext"):
        out = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True).stdout
        pages = out.split("\f")
        if pages and not pages[-1].strip():
            pages = pages[:-1]
        return [clean(p) for p in pages], "pdftotext"
    raise RuntimeError("no PDF reader available (install pdfplumber or pypdf)")


# ---------- Word ----------
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_units(path):
    try:
        import docx  # python-docx
        d = docx.Document(path)
        parts = []
        body = d.element.body
        for child in body.iterchildren():
            tag = child.tag.split("}")[-1]
            if tag == "p":
                txt = "".join(n.text or "" for n in child.iter(W + "t"))
                style = child.find(f"{W}pPr/{W}pStyle")
                sname = style.get(W + "val") if style is not None else ""
                if txt.strip():
                    parts.append(("# " if sname and sname.lower().startswith(("heading", "title")) else "") + txt)
            elif tag == "tbl":
                for row in child.iter(W + "tr"):
                    cells = ["".join(n.text or "" for n in c.iter(W + "t")).strip() for c in row.iter(W + "tc")]
                    parts.append(" | ".join(cells))
        return [clean("\n".join(parts))], "python-docx"
    except ImportError:
        pass
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    paras = ["".join(t.text or "" for t in p.iter(W + "t")) for p in root.iter(W + "p")]
    return [clean("\n".join(p for p in paras if p.strip()))], "zip-xml"


# ---------- PowerPoint ----------
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def pptx_units(path):
    try:
        from pptx import Presentation
        prs = Presentation(path)
        slides = []
        for s in prs.slides:
            parts = []
            for shp in s.shapes:
                if shp.has_text_frame:
                    parts.append(shp.text_frame.text)
                if getattr(shp, "has_table", False) and shp.has_table:
                    for r in shp.table.rows:
                        parts.append(" | ".join(c.text for c in r.cells))
            if s.has_notes_slide and s.notes_slide.notes_text_frame is not None:
                notes = s.notes_slide.notes_text_frame.text.strip()
                if notes:
                    parts.append("[speaker notes] " + notes)
            slides.append(clean("\n".join(parts)))
        return slides, "python-pptx"
    except ImportError:
        pass
    with zipfile.ZipFile(path) as z:
        names = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                       key=lambda n: int(re.findall(r"\d+", n)[-1]))
        slides = []
        for n in names:
            root = ET.fromstring(z.read(n))
            paras = ["".join(t.text or "" for t in p.iter(A + "t")) for p in root.iter(A + "p")]
            slides.append(clean("\n".join(p for p in paras if p.strip())))
    return slides, "zip-xml"


# ---------- Excel ----------
def xlsx_units(path):
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("openpyxl is needed for .xlsx (pip install openpyxl)")
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    sheets, names = [], []
    for ws in wb.worksheets:
        rows = []
        for r in ws.iter_rows(values_only=True):
            vals = ["" if v is None else str(v) for v in r]
            if any(v.strip() for v in vals):
                rows.append(" | ".join(vals).rstrip(" |"))
        sheets.append(clean("\n".join(rows)))
        names.append(ws.title)
    return sheets, "openpyxl", names


# ---------- HTML / text ----------
class _Text(HTMLParser):
    SKIP = {"script", "style", "nav", "footer", "header", "noscript"}
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "br", "section", "article", "table"}

    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_units(path):
    p = _Text()
    with open(path, encoding="utf-8", errors="replace") as f:
        p.feed(f.read())
    return [clean(html.unescape("".join(p.out)))], "html"


def text_units(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return [clean(f.read())], "text"


def extract(path):
    ext = os.path.splitext(path)[1].lower()
    labels = None
    if ext == ".pdf":
        units, how = pdf_pages(path)
        kind = "page"
    elif ext == ".docx":
        units, how = docx_units(path)
        kind = "document"
    elif ext == ".pptx":
        units, how = pptx_units(path)
        kind = "slide"
    elif ext == ".xlsx":
        units, how, labels = xlsx_units(path)
        kind = "sheet"
    elif ext in (".html", ".htm"):
        units, how = html_units(path)
        kind = "document"
    else:
        units, how = text_units(path)
        kind = "document"
    return units, kind, how, labels


def nice_title(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    return re.sub(r"[_]+", " ", stem).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", default="sources")
    ap.add_argument("--start", type=int, default=1, help="number of the first source id (s1, s2, ...)")
    a = ap.parse_args()

    files = []
    for inp in a.inputs:
        if os.path.isdir(inp):
            for root, _, names in os.walk(inp):
                for n in sorted(names):
                    if os.path.splitext(n)[1].lower() in SUPPORTED and not n.startswith("~$"):
                        files.append(os.path.join(root, n))
        elif os.path.isfile(inp):
            files.append(inp)
        else:
            print(f"not found: {inp}", file=sys.stderr)
    if not files:
        print("no supported files found", file=sys.stderr)
        return 2

    os.makedirs(a.out, exist_ok=True)
    manifest, n = [], a.start
    for path in files:
        ext = os.path.splitext(path)[1].lower()
        sid = f"s{n}"
        if ext not in SUPPORTED:
            print(f"skip {path}: unsupported type {ext}")
            continue
        try:
            units, kind, how, labels = extract(path)
        except Exception as e:
            print(f"FAILED {path}: {e}")
            continue
        n += 1
        low = [i + 1 for i, u in enumerate(units) if len(u) < LOW_TEXT] if kind in ("page", "slide") else []
        with open(os.path.join(a.out, sid + ".txt"), "w", encoding="utf-8") as f:
            f.write(f"### {sid}: {os.path.basename(path)}\n\n")
            for i, u in enumerate(units):
                if kind in ("page", "slide"):
                    f.write(f"=== {kind} {i + 1} ===\n")
                elif kind == "sheet":
                    f.write(f"=== sheet {labels[i]} ===\n")
                f.write(u + "\n\n")
        entry = {"id": sid, "title": nice_title(path), "file": os.path.basename(path), "unit": kind,
                 "units": len(units), "chars": sum(len(u) for u in units), "reader": how}
        if low:
            entry["emptyUnits"] = low
        manifest.append(entry)
        warn = ""
        if low:
            share = len(low) / max(1, len(units))
            warn = f"  ! {len(low)} {kind}s with little or no text{' (looks scanned: OCR needed)' if share > 0.5 else ''}: {compact(low)}"
        print(f"{sid}  {os.path.basename(path)}  {len(units)} {kind}(s), {entry['chars']:,} chars via {how}{warn}")

    with open(os.path.join(a.out, "sources.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nwrote {len(manifest)} source text files and sources.json to {a.out}/")
    print("\nsources array for the course JSON:")
    print(json.dumps([{"id": m["id"], "title": m["title"], "file": m["file"]} for m in manifest], ensure_ascii=False, indent=2))
    return 0


def compact(nums):
    out, start, prev = [], None, None
    for x in nums:
        if start is None:
            start = prev = x
        elif x == prev + 1:
            prev = x
        else:
            out.append(f"{start}" if start == prev else f"{start}-{prev}")
            start = prev = x
    if start is not None:
        out.append(f"{start}" if start == prev else f"{start}-{prev}")
    return ", ".join(out)


if __name__ == "__main__":
    sys.exit(main())
