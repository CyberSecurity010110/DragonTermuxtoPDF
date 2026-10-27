#!/usr/bin/env python3
"""
DragonTermuxtoPDF
=================
A Python tool that generates a comprehensive, human-readable PDF guide
containing the man pages of Termux packages.

Designed to run inside Termux on Android. On first run it automatically
checks for and installs missing dependencies (the `man` package and the
required Python modules) so you can just run:

    python TermuxtoPDF.py

The output PDF (termux_man_pages_guide.pdf) contains for every package
that ships a man page:
    * the package name
    * its usage (SYNOPSIS)
    * a detailed description (DESCRIPTION)
    * the complete, cleaned-up man page

A package index with page numbers is included at the end of the PDF.
Progress is shown live in the terminal and any failures are logged to
termux_manpdf_debug.log for easy debugging.
"""

import logging
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from fpdf import FPDF
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.panel import Panel
from rich.table import Table

console = Console()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OUTPUT_PDF = "termux_man_pages_guide.pdf"
LOG_FILE = "termux_manpdf_debug.log"
DEBUG_FILE = "man_pages_debug_raw.txt"

REQUIRED_PIP_PACKAGES = ["fpdf", "rich"]
REQUIRED_TERMUX_PACKAGES = ["man"]

FETCH_WORKERS = 4
MAN_FETCH_TIMEOUT = 30

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("DragonTermuxtoPDF")


# === Dependency management ===

def run_command(cmd, *, shell=False, timeout=60):
    """Run an external command and return a CompletedProcess-like object."""
    try:
        return subprocess.run(
            cmd, shell=shell, capture_output=True, text=True, timeout=timeout
        )
    except Exception as exc:
        log.exception("Command failed: %r", cmd)
        return None


def command_exists(cmd):
    """Return True if *cmd* can be found on PATH."""
    result = run_command(["sh", "-c", f"command -v {cmd}"])
    return result is not None and result.returncode == 0 and bool(result.stdout.strip())


def python_package_installed(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def pip_install(package):
    console.print(f"[yellow]Installing Python package [bold]{package}[/bold] via pip...[/yellow]")
    result = run_command(
        [sys.executable, "-m", "pip", "install", "--quiet", package], timeout=180
    )
    ok = result is not None and result.returncode == 0
    if not ok and result is not None:
        log.warning("pip install %s failed:\n%s", package, result.stderr)
    return ok


def termux_pkg_install(package):
    console.print(f"[yellow]Installing Termux package [bold]{package}[/bold] via pkg...[/yellow]")
    result = run_command(["pkg", "install", "-y", package], timeout=300)
    ok = result is not None and result.returncode == 0
    if not ok and result is not None:
        log.warning("pkg install %s failed:\n%s", package, result.stderr)
    return ok


def ensure_dependencies():
    """Check for required dependencies and auto-install anything that is missing."""
    missing = []

    for package in REQUIRED_PIP_PACKAGES:
        if not python_package_installed(package):
            missing.append(("pip", package))

    if command_exists("pkg"):
        for package in REQUIRED_TERMUX_PACKAGES:
            if not command_exists(package):
                missing.append(("pkg", package))
    else:
        console.print(
            "[bold yellow]Note:[/bold yellow] `pkg` was not found, so this does not appear to be "
            "Termux. Termux-specific packages cannot be auto-installed here; man page lookups "
            "will fail unless `man` is already available."
        )

    if not missing:
        console.print("[green]All required dependencies are satisfied.[/green]")
        return True

    console.print(
        Panel.fit(
            "[bold blue]Auto-installing missing dependencies[/bold blue]",
            subtitle="DragonTermuxtoPDF",
        )
    )
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Type", style="cyan")
    table.add_column("Package", style="green")
    for mtype, mname in missing:
        table.add_row(mtype, mname)
    console.print(table)

    for mtype, mname in missing:
        ok = pip_install(mname) if mtype == "pip" else termux_pkg_install(mname)
        if not ok:
            console.print(
                f"[red]Failed to install {mname}. Install it manually and re-run.[/red]"
            )
            log.error("Failed to install dependency: %s (%s)", mname, mtype)
            return False

    console.print("[green]All dependencies installed successfully.[/green]")
    return True


# === Package discovery ===

def get_all_packages():
    """Retrieve the list of all available Termux packages via `pkg list-all`."""
    console.print("[blue]Fetching the list of all available Termux packages...[/blue]")
    result = run_command(["pkg", "list-all"], timeout=120)
    if result is None or result.returncode != 0:
        console.print("[red]Failed to retrieve package list. Is `pkg` available?[/red]")
        log.error("pkg list-all failed: %s", result.stderr if result else "no result")
        return []

    packages = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # pkg list-all prints "package/version"
        name = line.split("/")[0].strip()
        if name:
            packages.append(name)

    packages = sorted(set(packages))
    console.print(f"[green]Found {len(packages)} available packages.[/green]")
    log.info("Discovered %d packages", len(packages))
    return packages


# === Man page text cleaning ===

UNICODE_TO_ASCII = {
    "\u2014": "-",
    "\u2013": "-",
    "\u2010": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201A": ",",
    "\u201C": '"',
    "\u201D": '"',
    "\u2022": "*",
    "\u2023": "*",
    "\u2026": "...",
    "\u00A0": " ",
    "\u00B7": "*",
    "\u2265": ">=",
    "\u2264": "<=",
    "\u00D7": "x",
    "\u00F7": "/",
}


def safe_text(text):
    """Return text safe for FPDF's core (Latin-1) fonts."""
    if not text:
        return ""
    for uni, ascii_ in UNICODE_TO_ASCII.items():
        text = text.replace(uni, ascii_)
    return text.encode("latin-1", "ignore").decode("latin-1")


def clean_man_text(text):
    """Strip man page control characters and return clean, readable text."""
    if not text:
        return ""

    # Remove ANSI escape sequences (colour, bold, etc.)
    text = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", text)
    text = re.sub(r"\x1b\].*?\x07", "", text)  # OSC sequences

    # Undo over-striking used by man for bold / underline:
    #   X\bX  -> X  (bold)
    #   _\bX  -> X  (underline)
    #   X\b_  -> X  (underline)
    text = re.sub(r"(.)\x08\1", r"\1", text)
    text = re.sub(r"_\x08(.)", r"\1", text)
    text = re.sub(r"(.)\x08_", r"\1", text)
    text = text.replace("\x08", "")  # remaining backspaces

    # Form feeds / carriage returns
    text = text.replace("\f", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "")

    # Remove leftover underscore underlining rules
    text = re.sub(r"_{2,}", "", text)

    # Collapse horizontal whitespace, keep line structure
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


SECTION_HEADING = re.compile(r"^([A-Z][A-Z/\- ]{2,})$")


def split_man_sections(text):
    """Split a cleaned man page into (heading, body) chunks."""
    sections = []
    current_heading = None
    buffer = []

    for line in text.split("\n"):
        stripped = line.strip()
        if SECTION_HEADING.match(stripped) and len(stripped) < 45:
            if current_heading is not None:
                sections.append((current_heading, "\n".join(buffer).strip()))
            current_heading = stripped
            buffer = []
        else:
            buffer.append(line)

    if current_heading is not None:
        sections.append((current_heading, "\n".join(buffer).strip()))
    elif buffer:
        sections.append((None, "\n".join(buffer).strip()))

    return sections


def extract_section(text, wanted):
    """Return the body of a named man section (case-insensitive), or None."""
    for heading, body in split_man_sections(text):
        if heading and heading.lower() == wanted.lower():
            return body
    return None


# === Man page fetching ===

def fetch_man_page(package):
    """Fetch and clean the man page for a single package."""
    try:
        result = run_command(["man", package], timeout=MAN_FETCH_TIMEOUT)
        if result is None or result.returncode != 0 or not result.stdout.strip():
            return None
        return clean_man_text(result.stdout)
    except Exception as exc:
        log.exception("Failed to fetch man page for %s", package)
        return None


def fetch_all_man_pages(packages):
    """Fetch man pages for every package in parallel."""
    results = {}
    failed = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        fetch_task = progress.add_task("[cyan]Fetching man pages...", total=len(packages))

        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as executor:
            future_to_package = {
                executor.submit(fetch_man_page, package): package
                for package in packages
            }
            for future in as_completed(future_to_package):
                package = future_to_package[future]
                try:
                    content = future.result()
                except Exception as exc:  # pragma: no cover
                    log.exception("Unexpected error while fetching %s", package)
                    content = None

                results[package] = content
                if content is None:
                    failed.append(package)

                progress.update(
                    fetch_task,
                    description=f"[cyan]Fetching {package}...",
                    advance=1,
                )

    return results, failed


# === PDF generation ===

class TermuxManPDF(FPDF):
    """PDF document for the Termux man page guide."""

    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(15, 15, 15)
        self.package_index = []  # (package_name, page_number)

    def header(self):
        if self.page_no() == 1:
            return  # title page has no running header
        self.set_font("Arial", "B", 10)
        self.set_text_color(40, 40, 40)
        self.cell(0, 7, "DragonTermuxtoPDF - Termux Package Man Pages", align="C", ln=True)
        self.set_font("Arial", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, f"Generated: {datetime.now():%Y-%m-%d %H:%M}", align="C", ln=True)
        self.ln(3)

    def footer(self):
        self.set_y(-12)
        self.set_font("Arial", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, f"Page {self.page_no()}", align="C")

    def chapter_title(self, text, size=13):
        self.set_font("Arial", "B", size)
        self.set_text_color(30, 60, 110)
        self.cell(0, 8, safe_text(text), ln=True)
        self.set_draw_color(30, 60, 110)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def section_heading(self, text):
        self.set_font("Arial", "B", 11)
        self.set_text_color(50, 50, 50)
        self.cell(0, 6, safe_text(text), ln=True)
        self.ln(1)

    def body_text(self, text, size=9, font="Courier"):
        self.set_font(font, "", size)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 4.2, safe_text(text))
        self.ln(2)

    def body_paragraph(self, text, size=9, font="Arial"):
        self.set_font(font, "", size)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 4.2, safe_text(text))
        self.ln(2)

    def add_title_page(self, total_scanned, with_man):
        self.add_page()
        self.ln(50)
        self.set_font("Arial", "B", 26)
        self.set_text_color(30, 60, 110)
        self.cell(0, 15, "DragonTermuxtoPDF", align="C", ln=True)
        self.ln(2)
        self.set_font("Arial", "B", 16)
        self.set_text_color(60, 60, 60)
        self.cell(0, 10, "Termux Package Man Page Guide", align="C", ln=True)
        self.ln(12)
        self.set_font("Arial", "", 11)
        self.set_text_color(90, 90, 90)
        self.cell(
            0,
            7,
            "A comprehensive reference of man pages for available Termux packages",
            align="C",
            ln=True,
        )
        self.cell(0, 7, f"Packages scanned: {total_scanned}", align="C", ln=True)
        self.cell(0, 7, f"Packages with man pages: {with_man}", align="C", ln=True)
        self.cell(0, 7, f"Generated: {datetime.now():%Y-%m-%d %H:%M}", align="C", ln=True)
        self.cell(0, 7, "Platform: Termux (Android)", align="C", ln=True)
        self.ln(18)
        self.set_font("Arial", "I", 9)
        self.multi_cell(
            0,
            6,
            safe_text(
                "Each package section lists the package name, its usage (SYNOPSIS), a "
                "detailed description (DESCRIPTION), and the complete man page. "
                "Packages without an available man page are logged to "
                "man_pages_debug_raw.txt."
            ),
            align="C",
        )

    def add_contents(self, total_scanned, with_man, without_man):
        self.add_page()
        self.chapter_title("Contents")
        self.body_paragraph(
            "This guide contains man page references for Termux packages. Every package "
            "that ships a man page has its own section showing the package name, usage "
            "(SYNOPSIS), description (DESCRIPTION), and the full man page text.",
            size=9,
        )
        self.ln(6)
        self.section_heading("Generation summary")
        self.body_paragraph(
            f"Packages scanned:   {total_scanned}\n"
            f"With man pages:     {with_man}\n"
            f"Without man pages:  {without_man}\n"
            f"Output file:        {OUTPUT_PDF}",
            size=9,
            font="Courier",
        )
        self.ln(8)
        self.section_heading("How to read this guide")
        self.body_paragraph(
            "Package sections are arranged alphabetically and each begins on a new page. "
            "See the Package Index at the end of this document to jump directly to a "
            "specific package.",
            size=9,
        )


# === generate_pdf ===

def generate_pdf(packages_with_man, total_scanned, without_man, man_contents):
    """Render the man page guide to OUTPUT_PDF."""
    pdf = TermuxManPDF()
    pdf.set_title("Termux Package Man Page Guide")
    pdf.set_author("DragonTermuxtoPDF")

    pdf.add_title_page(total_scanned, len(packages_with_man))
    pdf.add_contents(total_scanned, len(packages_with_man), without_man)

    log.info("Rendering %d package sections into PDF", len(packages_with_man))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        render_task = progress.add_task(
            "[green]Generating PDF pages...", total=len(packages_with_man)
        )

        for package in packages_with_man:
            progress.update(render_task, description=f"[green]Rendering {package}...")

            pdf.add_page()
            pdf.package_index.append((package, pdf.page_no()))

            pdf.chapter_title(f"Package: {package}")
            pdf.ln(2)

            content = man_contents[package]

            pdf.section_heading("Usage (SYNOPSIS)")
            synopsis = extract_section(content, "SYNOPSIS")
            pdf.body_paragraph(
                synopsis or "No SYNOPSIS section found in this man page.",
                size=9,
                font="Courier",
            )

            pdf.section_heading("Description (DESCRIPTION)")
            description = extract_section(content, "DESCRIPTION")
            pdf.body_paragraph(
                description or "No DESCRIPTION section found in this man page.",
                size=9,
                font="Courier",
            )

            pdf.section_heading("Complete Man Page")
            pdf.body_text(content, size=8)

            pdf.ln(2)
            progress.update(render_task, advance=1)

    # ---- Package index (at the end) ----
    pdf.add_page()
    pdf.chapter_title("Package Index")
    pdf.body_paragraph(
        "Each package section below starts on the page number shown. Sections appear in "
        "the same order in this guide.", size=9
    )
    pdf.ln(4)
    pdf.set_font("Courier", "", 8)
    for package, page in pdf.package_index:
        pdf.cell(0, 5, safe_text(f"{package} .... page {page}"), ln=True)

    pdf.output(OUTPUT_PDF)
    log.info("PDF written to %s", OUTPUT_PDF)
    console.print(f"\n[bold green]PDF generated successfully:[/bold green] {OUTPUT_PDF}")


def main():
    console.print(
        Panel.fit(
            "[bold blue]DragonTermuxtoPDF[/bold blue]\nTermux Package Man Page Guide",
            subtitle="🐉📱📄",
        )
    )

    if not ensure_dependencies():
        console.print("[red]Aborting: required dependencies are missing.[/red]")
        sys.exit(1)

    packages = get_all_packages()
    if not packages:
        console.print("[red]No packages found. Exiting.[/red]")
        sys.exit(1)

    console.print(
        f"[blue]Fetching man pages for {len(packages)} packages (this may take a while)...[/blue]"
    )
    man_contents, failed = fetch_all_man_pages(packages)

    # Write raw debug dump for every package
    with open(DEBUG_FILE, "w", encoding="utf-8") as debug:
        debug.write(f"DragonTermuxtoPDF debug dump - {datetime.now():%Y-%m-%d %H:%M}\n")
        debug.write(f"Packages scanned: {len(packages)}\n")
        debug.write(
            f"Packages with man pages: {sum(1 for c in man_contents.values() if c)}\n"
        )
        debug.write("=" * 70 + "\n\n")
        for package in sorted(packages):
            debug.write(f"\n{'='*15} Package: {package} {'='*15}\n\n")
            content = man_contents.get(package)
            if content:
                debug.write(content)
            else:
                debug.write("[No man page available]\n")
            debug.write("\n\n")
    log.info("Debug dump written to %s", DEBUG_FILE)

    packages_with_man = sorted([p for p in packages if man_contents.get(p)])
    without_man = [p for p in packages if not man_contents.get(p)]

    console.print(
        f"[blue]Rendering {len(packages_with_man)} packages with man pages into PDF...[/blue]"
    )
    if without_man:
        console.print(
            f"[yellow]{len(without_man)} packages have no available man page "
            f"(listed in {DEBUG_FILE}).[/yellow]"
        )

    generate_pdf(packages_with_man, len(packages), len(without_man), man_contents)

    console.print(f"[bold blue]Log / debug files:[/bold blue] {LOG_FILE} / {DEBUG_FILE}")
    if failed:
        console.print(
            f"[red]{len(failed)} packages failed during fetch; see {LOG_FILE} for details.[/red]"
        )


if __name__ == "__main__":
    main()
