# DragonTermuxtoPDF 🐉📱📄

A powerful Python tool that generates a comprehensive PDF containing man pages for all available Termux packages (not just installed ones). This tool provides a complete reference of Termux package documentation in a well-structured, readable format.

## ✨ Features

- 📚 Generates a single PDF containing man pages for ALL available Termux packages
- 🔍 Uses `pkg list-all` to get a complete list of available packages
- 🚀 Parallel processing for faster execution
- 📊 Real-time progress tracking with dual progress bars
- 🎨 Well-formatted output with proper typography
- 📑 Hierarchical structure with package and man page organization
- 🛠️ Error handling and recovery
- 💾 Efficient memory management

## 🔧 Requirements

- Termux app installed on Android
- Python 3.x
- Required Python packages:
  ```bash
  pip install fpdf rich

📥 Installation

    Clone the repository:

bash

git clone https://github.com/CyberSecurity010110/DragonTermuxtoPDF.git

    Navigate to the project directory:

bash

cd DragonTermuxtoPDF

    Install required packages:

bash

pip install -r requirements.txt

🚀 Usage

Simply run the script:

bash

python TermuxtoPDF.py

The script will:

    Fetch a complete list of ALL available Termux packages using pkg list-all
    Attempt to retrieve man pages for each package
    Generate a well-formatted PDF file named termux_man_pages.pdf

📋 Output

The generated PDF includes:

    Title page
    Package-wise organization
    Well-formatted man pages
    Page numbers
    Table of contents
    Clear section formatting

🎯 Progress Tracking

The tool provides real-time progress information:

    Package discovery progress
    Man page fetching progress
    PDF generation progress
    Error notifications for missing man pages

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

🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

🙏 Acknowledgments

    FPDF for PDF generation
    Rich for beautiful terminal formatting
    Termux for the amazing terminal emulator



  
