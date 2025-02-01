#!/usr/bin/env python3
import os
import subprocess
from fpdf import FPDF
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
import threading
from queue import Queue
import re

console = Console()

class PDF(FPDF):
    def header(self):
        self.set_font("Arial", 'B', size=12)
        self.cell(0, 10, "Man Pages for Termux Packages", ln=True, align="C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", size=8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")
    
    def chapter_title(self, title):
        self.set_font("Arial", 'B', size=12)
        self.cell(0, 10, title, ln=True)
        self.ln(5)
    
    def chapter_body(self, text):
        self.set_font("Courier", size=10)
        # Process the text to improve formatting
        formatted_text = self.format_man_page(text)
        self.multi_cell(0, 5, formatted_text)
        self.ln()

    def format_man_page(self, text):
        # Remove ANSI escape sequences
        text = re.sub(r'\x1b\[[0-9;]*m', '', text)
        
        # Improve section formatting
        sections = re.split(r'\n(?=\S+\n=+\n)', text)
        formatted_sections = []
        
        for section in sections:
            # Add extra newlines between sections
            section = section.strip()
            formatted_sections.append(section + "\n\n")
        
        return "\n".join(formatted_sections)

def get_all_packages():
    """Retrieve the list of all available Termux packages."""
    console.print("[blue]Fetching the list of all Termux packages...[/blue]")
    result = subprocess.run(["pkg", "list-all"], capture_output=True, text=True)
    if result.returncode != 0:
        console.print("[red]Failed to retrieve package list.[/red]")
        return []
    packages = [line.split("/")[0] for line in result.stdout.splitlines() if line]
    return sorted(set(packages))

def get_package_man_pages(package):
    """Get all available man pages for a package."""
    try:
        # First, try to find man pages in the package
        result = subprocess.run(["dpkg", "-L", package], capture_output=True, text=True)
        if result.returncode == 0:
            man_files = [line for line in result.stdout.splitlines() 
                        if '/man/' in line and not line.endswith('.gz')]
            return man_files
    except Exception:
        pass
    return []

def fetch_man_page(man_path):
    """Fetch the content of a man page."""
    try:
        result = subprocess.run(["man", man_path], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout
    except Exception:
        pass
    return None

class PDFGenerator:
    def __init__(self):
        self.pdf = PDF()
        self.pdf.set_auto_page_break(auto=True, margin=15)
        self.queue = Queue()
        self.lock = threading.Lock()

    def process_package(self, package, progress, task_id):
        man_pages = get_package_man_pages(package)
        if not man_pages:
            # Try direct man page fetch if no files found
            content = fetch_man_page(package)
            if content:
                self.queue.put((package, {package: content}))
            progress.update(task_id, advance=1)
            return

        package_pages = {}
        for man_path in man_pages:
            content = fetch_man_page(man_path)
            if content:
                name = os.path.basename(man_path)
                package_pages[name] = content
        
        if package_pages:
            self.queue.put((package, package_pages))
        progress.update(task_id, advance=1)

    def generate_pdf(self, packages):
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            # Create tasks for both phases
            fetch_task = progress.add_task("[blue]Fetching man pages...", total=len(packages))
            pdf_task = progress.add_task("[green]Generating PDF...", total=len(packages))

            # Create threads for parallel processing
            threads = []
            for package in packages:
                thread = threading.Thread(
                    target=self.process_package,
                    args=(package, progress, fetch_task)
                )
                thread.start()
                threads.append(thread)

            # Process results as they come in
            processed = 0
            while processed < len(packages):
                try:
                    package, pages = self.queue.get(timeout=1)
                    with self.lock:
                        self.pdf.add_page()
                        self.pdf.chapter_title(f"Package: {package}")
                        
                        for page_name, content in pages.items():
                            self.pdf.chapter_title(f"Man page: {page_name}")
                            self.pdf.chapter_body(content)
                    
                    progress.update(pdf_task, advance=1)
                    processed += 1
                except Exception:
                    if all(not t.is_alive() for t in threads):
                        break

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

        output_file = "termux_man_pages.pdf"
        self.pdf.output(output_file)
        console.print(f"[bold green]PDF generated successfully: {output_file}[/bold green]")

def main():
    packages = get_all_packages()
    if not packages:
        console.print("[red]No packages found. Exiting...[/red]")
        return
    
    pdf_generator = PDFGenerator()
    pdf_generator.generate_pdf(packages)

if __name__ == "__main__":
    main()
