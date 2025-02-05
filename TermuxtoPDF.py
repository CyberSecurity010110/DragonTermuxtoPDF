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
        title = "Man Pages for Termux Packages"
        if hasattr(self, 'current_package'):
            title += f" ({self.current_package})"
        self.cell(0, 10, title, ln=True, align="C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", size=8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def set_current_package(self, package):
        self.current_package = package

    def chapter_title(self, title):
        self.set_font("Arial", 'B', size=12)
        self.cell(0, 10, title, ln=True)
        self.ln(5)

    def chapter_body(self, text):
        self.set_font("Courier", size=10)
        
        # Set left margin for better readability
        original_margin = self.l_margin
        self.set_left_margin(15)
        
        # Process the text to improve formatting
        formatted_text = self.improved_format_man_page(text)
        
        # Split text into paragraphs
        paragraphs = formatted_text.split('\n\n')
        
        for paragraph in paragraphs:
            # Check if this is a section header
            if re.match(r'^[A-Z][A-Z\s]+$', paragraph.strip()):
                self.set_font("Arial", 'B', size=11)
                self.ln(5)
                self.multi_cell(0, 5, paragraph)
                self.ln(2)
                self.set_font("Courier", size=10)
            else:
                self.multi_cell(0, 5, paragraph)
                self.ln(2)
        
        # Restore original margin
        self.set_left_margin(original_margin)

    def improved_format_man_page(self, text):
        if not text:
            return ""
        
        # Basic cleanup
        text = re.sub(r'\x1b\[[0-9;]*m', '', text)  # Remove ANSI sequences
        text = text.replace('\f', '')  # Remove form feed
        text = re.sub(r'_+', '', text)  # Remove underscores
        text = re.sub(r'(.)\1', r'\1', text)  # Remove doubled characters
        
        # Normalize spaces and line endings
        text = re.sub(r'[ \t]+', ' ', text)
        text = text.replace('\r\n', '\n')
        
        # Process sections
        lines = text.split('\n')
        processed_lines = []
        in_section_header = False
        
        for line in lines:
            # Clean the line
            line = line.rstrip()
            
            # Check if it's a section header
            if re.match(r'^[A-Z][A-Z\s]+$', line):
                in_section_header = True
                processed_lines.extend(['', line, '-' * 40, ''])
            else:
                if line:
                    processed_lines.append(line)
        
        text = '\n'.join(processed_lines)
        
        # Final cleanup
        text = re.sub(r'\n{3,}', '\n\n', text)  # Remove excess blank lines
        return text

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
        # Use col to remove formatting characters
        result = subprocess.run(
            f"man {man_path} | col -b",
            shell=True,
            capture_output=True,
            text=True
        )
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
        self.processed_count = 0
        self.total_packages = 0
        self.failed_packages = []
        self.packages_with_man = []
        self.total_man_pages = 0

    def process_package(self, package, progress, task_id):
        try:
            man_pages = get_package_man_pages(package)
            has_content = False
            
            if not man_pages:
                content = fetch_man_page(package)
                if content:
                    self.queue.put((package, {package: content}))
                    has_content = True
            else:
                package_pages = {}
                for man_path in man_pages:
                    content = fetch_man_page(man_path)
                    if content:
                        name = os.path.basename(man_path)
                        package_pages[name] = content
                        has_content = True
                
                if package_pages:
                    self.queue.put((package, package_pages))
            
            with self.lock:
                self.processed_count += 1
                if has_content:
                    self.packages_with_man.append(package)
                progress.update(task_id, completed=self.processed_count)
                
        except Exception as e:
            self.failed_packages.append((package, str(e)))
            with self.lock:
                self.processed_count += 1
                progress.update(task_id, completed=self.processed_count)

    def generate_pdf(self, packages):
        self.total_packages = len(packages)
        debug_file = "man_pages_debug.txt"
        
        console.print(f"[blue]Processing {self.total_packages} packages...[/blue]")
        
        # Clear debug file
        with open(debug_file, 'w', encoding='utf-8') as debug:
            debug.write(f"Starting processing of {self.total_packages} packages\n")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
            refresh_per_second=1
        ) as progress:
            fetch_task = progress.add_task(
                "[blue]Fetching man pages...",
                total=self.total_packages
            )
            pdf_task = progress.add_task(
                "[green]Generating PDF...",
                total=self.total_packages
            )
            
            # Process packages in smaller batches
            batch_size = 50
            total_processed = 0
            
            for i in range(0, len(packages), batch_size):
                batch = packages[i:i + batch_size]
                threads = []
                
                console.print(f"[cyan]Processing batch {(i//batch_size)+1} ({i+1}-{min(i+batch_size, self.total_packages)}/{self.total_packages})[/cyan]")
                
                for package in batch:
                    thread = threading.Thread(
                        target=self.process_package,
                        args=(package, progress, fetch_task)
                    )
                    thread.start()
                    threads.append(thread)
                
                pdf_processed = 0
                with open(debug_file, 'a', encoding='utf-8') as debug:
                    while pdf_processed < len(batch):
                        try:
                            package, pages = self.queue.get(timeout=1)
                            with self.lock:
                                self.pdf.set_current_package(package)
                                self.pdf.add_page()
                                self.pdf.chapter_title(f"Package: {package}")
                                
                                debug.write(f"\n{'='*50}\nPackage: {package}\n{'='*50}\n")
                                
                                for page_name, content in pages.items():
                                    self.pdf.chapter_title(f"Man page: {page_name}")
                                    self.pdf.chapter_body(content)
                                    self.total_man_pages += 1
                                    
                                    debug.write(f"\n{'-'*30}\nMan page: {page_name}\n{'-'*30}\n")
                                    debug.write(content)
                                    debug.write("\n\n")
                                
                                debug.flush()
                            
                            pdf_processed += 1
                            total_processed += 1
                            progress.update(pdf_task, completed=total_processed)
                            
                        except Exception as e:
                            if all(not t.is_alive() for t in threads):
                                break
                            console.print(f"[red]Error processing package: {e}[/red]")
                
                for thread in threads:
                    thread.join()
        
        output_file = "termux_man_pages.pdf"
        self.pdf.output(output_file)
        
        # Print summary
        console.print("\n[bold blue]Processing Summary:[/bold blue]")
        console.print(f"Total packages processed: {self.total_packages}")
        console.print(f"Packages with man pages: {len(self.packages_with_man)}")
        console.print(f"Total man pages found: {self.total_man_pages}")
        console.print(f"Failed packages: {len(self.failed_packages)}")
        
        console.print(f"\n[bold green]PDF generated successfully: {output_file}[/bold green]")
        console.print(f"[bold blue]Debug output written to: {debug_file}[/bold blue]")
        
        if self.failed_packages:
            console.print("\n[yellow]Failed packages:[/yellow]")
            for package, error in self.failed_packages:
                console.print(f"[red]{package}: {error}[/red]")

def main():
    packages = get_all_packages()
    if not packages:
        console.print("[red]No packages found. Exiting...[/red]")
        return
    
    pdf_generator = PDFGenerator()
    pdf_generator.generate_pdf(packages[:])

if __name__ == "__main__":
    main()
