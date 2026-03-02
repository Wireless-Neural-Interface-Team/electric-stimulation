# Electric stimulation
GUI to generate and modify a electric trigger send to a national instrument wich converts this to a electric stimulation signal designed for neurostimulation with a micro-electrode array.

**Multi-platform:** Windows, macOS, Linux.

The library is available on PyPI.

## Installation (PyPI)
1. Open terminal as administrator
2. Run on terminal [uv](https://docs.astral.sh/uv/): `curl -LsSf https://astral.sh/uv/install.sh | sh` (macOS/Linux) or `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` (Windows)
3. Install virtual environment : run in terminal `uv venv si_env --python 3.12`
4. Restart your terminal
5. Allow script execution : run in terminal `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned`
6. Activate virtual environment: run in terminal `source si_env/bin/activate` (macOS/Linux) or `si_env\Scripts\activate` (Windows)
7. Install library : run in terminal `uv pip install electric-stimulation`

## Run application
1. Allow script execution : run in terminal `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned`
2. Activate virtual environment: run in terminal `source si_env/bin/activate` (macOS/Linux) or `si_env\Scripts\activate` (Windows)
3. Run in terminal `trigger-generator`

## Build a standalone executable (Windows: `.exe`, macOS/Linux: binary):
1. Allow script execution : run in terminal `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned`
2. Activate virtual environment: run in terminal `source si_env/bin/activate` (macOS/Linux) or `si_env\Scripts\activate` (Windows) 
3. Using the command-line terminal, navigate to the folder where you want the .exe file to be located.
4. Build the executable in currentfolder/dist : run in terminal `trigger-generator-build`

The executable will be in `dist/` (in the current directory).
