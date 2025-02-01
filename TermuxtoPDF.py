#!/usr/bin/env python3

import os
import subprocess
from fpdf import FPDF
from rich.console import Console

console = Console()

# Initialize PDF object
class PDF(FPDF):
    def header(self):
        self.set_font("Arial", size=12)
        self.cell(0, 10, "Man Pages for Termux Packages", ln=True, align="C")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", size=8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

pdf = PDF()
pdf.set_auto_page_break(auto=True, margin=15)

def get_all_packages():
    """Retrieve the list of all available Termux packages."""
    console.print("[blue]Fetching the list of all Termux packages...[/blue]")
    result = subprocess.run(["pkg", "list-all"], capture_output=True, text=True)
    if result.returncode != 0:
        console.print("[red]Failed to retrieve package list.[/red]")
        return []
    packages = [line.split("/")[0] for line in result.stdout.splitlines() if line]
    return sorted(set(packages))

def fetch_man_page(package):
    """Fetch the man page for a given package."""
    try:
        result = subprocess.run(["man", package], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout
        else:
            return None
    except Exception as e:
        console.print(f"[red]Error fetching man page for {package}: {e}[/red]")
        return None

def generate_pdf(packages):
    """Generate a PDF with the man pages for all packages."""
    console.print("[blue]Generating PDF of man pages...[/blue]")
    
    for package in packages:
        console.print(f"[green]Processing: {package}[/green]")
        man_page = fetch_man_page(package)
        
        if man_page:
            pdf.add_page()
            pdf.set_font("Courier", size=10)
            pdf.multi_cell(0, 10, f"Man Page for: {package}\n\n{man_page}")
        else:
            console.print(f"[yellow]No man page found for {package}. Skipping...[/yellow]")

    output_file = "termux_man_pages.pdf"
    pdf.output(output_file)
    console.print(f"[bold green]PDF generated successfully: {output_file}[/bold green]")

def main():
    packages = get_all_packages()
    if not packages:
        console.print("[red]No packages found. Exiting...[/red]")
        return
    generate_pdf(packages)

if __name__ == "__main__":
    main()
