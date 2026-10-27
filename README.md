# DragonTermuxtoPDF 🐉📱📄

A powerful Python tool that generates a comprehensive PDF containing man pages for all available Termux packages (not just installed ones). This tool provides a complete reference of Termux package documentation in a well-structured, readable format.

## ✨ Features

- 📚 Generates a single PDF containing man pages for Termux packages that ship a man page on the system — a complete, readable reference of Termux package documentation
- 🔍 Uses `pkg list-all` to discover all available packages
- 🚀 Parallel fetching of man pages for faster execution
- 📊 Real-time progress bar showing exactly which package is being fetched or rendered
- 🎨 Well-formatted output: title page, contents, per-package sections, page numbers
- 📑 Per-package structure: package name, usage (SYNOPSIS), description (DESCRIPTION), full man page
- 📑 Package index with page numbers at the end of the PDF
- 🔧 Auto-installs missing dependencies (`fpdf`, `rich` via pip; `man` via `pkg`)
- 🛠️ Error handling and recovery, with per-package failure reporting
- 🪵 Logging to `termux_manpdf_debug.log` and a raw debug dump (`man_pages_debug_raw.txt`)
- 💾 Efficient memory management

## 🔧 Requirements

- Termux app installed on Android
- Python 3.x
- Required Python packages:
  pip install fpdf rich
- Termux package: `man` (auto-installed if missing)

📥 Installation

    Clone the repository:

git clone https://github.com/CyberSecurity010110/DragonTermuxtoPDF.git

    Navigate to the project directory:

cd DragonTermuxtoPDF

    Install required packages:

    pip install -r requirements.txt

🚀 Usage

Simply run the script:

python TermuxtoPDF.py

The script will:

    Check and auto-install missing dependencies (fpdf, rich via pip; man via pkg)
    Fetch a complete list of available Termux packages using pkg list-all
    Attempt to retrieve man pages for each package (in parallel)
    Generate a well-formatted PDF file named termux_man_pages_guide.pdf

📋 Output

The generated PDF (`termux_man_pages_guide.pdf`) includes:

    Title page with generation stats
    Contents summary (packages scanned / with man pages / without)
    One section per package with man pages, each starting on a new page:
        * Package name
        * Usage (SYNOPSIS)
        * Description (DESCRIPTION)
        * Complete, cleaned-up man page
    Page numbers in the footer
    Package index with page numbers at the end of the document

🎯 Progress Tracking

A live progress bar shows exactly what is happening:

    Fetching man pages: current package name and overall progress
    Generating PDF pages: current package name and overall progress
    Time elapsed is shown for both stages

Packages without an available man page are reported at the end and listed in the debug dump.

⚠️ Known Limitations

    Processing time depends on the total number of available packages
    PDF file size varies based on available man pages
    Some packages might not have man pages available

🛠️ Troubleshooting

If you encounter issues:

    Ensure required packages are installed:
    pkg update && pkg upgrade
    pkg install python man

    Verify Python package installation:
    pip list | grep -E "fpdf|rich"

    If the package list isn't loading
    pkg update

🔧 Auto-installation

On first run the script checks for the Python modules `fpdf` and `rich` (installed via `pip`) and the
Termux package `man` (installed via `pkg install man`). Anything missing is installed automatically
before the PDF is built. If you are not running inside Termux, the Termux-specific step is skipped.

🪵 Logging

All activity is logged to `termux_manpdf_debug.log` for easy debugging. A raw per-package dump of every
fetched man page (or "No man page available") is written to `man_pages_debug_raw.txt`. Failed packages
are listed in the console at the end of the run and in the log file.

🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

🙏 Acknowledgments

    FPDF for PDF generation
    Rich for beautiful terminal formatting
    Termux for the amazing terminal emulator



  
