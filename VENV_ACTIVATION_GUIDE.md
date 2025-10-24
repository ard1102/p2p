# Python Virtual Environment Activation Guide

## Virtual Environment Created Successfully!

A Python virtual environment has been created in the `.venv` directory with the following specifications:

- **Environment Directory**: `.venv`
- **Python Version**: 3.11.9
- **Pip Version**: 25.2 (latest)
- **System Site Packages**: Disabled (`include-system-site-packages = false`)
- **Platform**: Windows

## Activation Scripts Available

The following activation scripts have been generated in `.venv\Scripts\`:

### For Windows PowerShell:
```powershell
.venv\Scripts\Activate.ps1
```

### For Windows Command Prompt:
```cmd
.venv\Scripts\activate.bat
```

### For Unix/Linux/MacOS (bash/zsh):
```bash
source .venv/bin/activate
```

## How to Activate the Virtual Environment

### Current Shell Session Activation:

#### For PowerShell (Current Terminal):
```powershell
.venv\Scripts\Activate.ps1
```

#### For Command Prompt:
```cmd
.venv\Scripts\activate.bat
```

### Verification:
After activation, you should see the virtual environment name in your prompt:
```
(.venv) C:\Users\arake\Downloads\Rough\p2p>
```

You can also verify by checking the Python path:
```bash
which python  # On Unix/Linux/MacOS
where python  # On Windows
```

## Package Installation

Once activated, you can install packages using pip:
```bash
pip install package_name
```

## Deactivation

To deactivate the virtual environment and return to your system Python:
```bash
deactivate
```

## Environment Structure

```
.venv/
├── Include/                    # C headers
├── Lib/                        # Python libraries
│   └── site-packages/        # Installed packages
├── Scripts/                    # Executables and activation scripts
│   ├── Activate.ps1           # PowerShell activation
│   ├── activate                 # Unix activation (if cross-platform)
│   ├── activate.bat            # Windows Command Prompt activation
│   ├── deactivate.bat          # Windows deactivation
│   ├── python.exe              # Python interpreter
│   ├── pip.exe                 # pip package manager
│   └── ...
└── pyvenv.cfg                  # Environment configuration
```

## Ready for Development!

Your virtual environment is now ready for immediate use. You can start installing packages and developing your Python applications with an isolated environment.