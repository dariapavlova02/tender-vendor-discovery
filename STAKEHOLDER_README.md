# Stakeholder Launch Guide

This guide explains how a non-technical stakeholder can open the Tender Vendor AI dashboard on macOS or Windows. The project folder you receive already contains the `.env` file with API keys, so you only need to run one script.

## What you need

- A computer with **Python 3.10 or newer** installed. (The default Python that ships with macOS 12+ works; Windows users can install Python from [python.org](https://www.python.org/downloads/windows/).)
- An internet connection for the first launch (the script downloads Python packages once).
- The project folder exactly as delivered (do not rename internal files, keep the `.env`).

## macOS

1. Download/unzip the project and open the folder in Finder.
2. Double-click `start_dashboard_mac.sh`. (If Gatekeeper blocks it, right-click → `Open`.)
3. A Terminal window appears, installs dependencies the first time (1-2 minutes), and then shows `Starting dashboard -> http://localhost:8501`. Open that link in a browser.

> The script creates a `.dashboard-venv` folder inside the project. Do not delete it unless you want to force a clean reinstall.

## Windows

1. Download/unzip the project and open the folder in File Explorer.
2. Double-click `start_dashboard_windows.bat`.
3. A Command Prompt window appears, installs dependencies the first time, and then keeps running Streamlit. Open `http://localhost:8501` in your browser.

> Windows may warn about “running scripts downloaded from the internet.” Choose **Run anyway** – the script only installs Python packages locally.

## What the scripts do

- Verify that Python 3.10+ is installed.
- Ensure the `.env` file with API keys is present (otherwise they stop and ask you to add it).
- Create a private virtual environment in `.dashboard-venv`.
- Install project dependencies inside that environment (first run only).
- Launch the Streamlit dashboard so you can work in the browser.

## Troubleshooting

- **Python missing**: Install Python 3.10+ from python.org, then run the script again.
- **Port already in use**: Close any other Streamlit apps or change the `STREAMLIT_SERVER_PORT` environment variable before launching.
- **Need a clean reinstall**: Delete the `.dashboard-venv` folder and run the script again; it will rebuild everything automatically.

If you run into an error screen, copy the text from the Terminal/Command Prompt window and share it with the engineering team.
