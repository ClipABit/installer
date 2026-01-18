#!/usr/bin/env python3
"""
ClipABit Plugin Installer for DaVinci Resolve
This script installs the ClipABit plugin for DaVinci Resolve on macOS.
"""

import sys
import os
import subprocess
import shutil
import platform
from pathlib import Path

# For reading pyproject.toml
try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Fallback for Python 3.8-3.10
    except ImportError:
        tomllib = None
class Colors:
    """Terminal colors for pretty output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(message):
    """Print a header message."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")


def print_success(message):
    """Print a success message."""
    print(f"{Colors.OKGREEN}✓ {message}{Colors.ENDC}")


def print_error(message):
    """Print an error message."""
    print(f"{Colors.FAIL}✗ {message}{Colors.ENDC}")


def print_warning(message):
    """Print a warning message."""
    print(f"{Colors.WARNING}⚠ {message}{Colors.ENDC}")


def print_info(message):
    """Print an info message."""
    print(f"{Colors.OKCYAN}ℹ {message}{Colors.ENDC}")


def check_platform():
    """Check if running on a supported platform."""
    system = platform.system()
    if system == "Darwin":
        print_success(f"Running on macOS {platform.mac_ver()[0]}")
        return True
    elif system == "Windows":
        print_success(f"Running on Windows {platform.version()}")
        return True
    else:
        print_error(f"Unsupported platform: {system}")
        print_info("This installer supports macOS and Windows only.")
        return False


def check_davinci_resolve():
    """Check if DaVinci Resolve is installed."""
    print_info("Checking for DaVinci Resolve installation...")
    
    system = platform.system()
    
    if system == "Darwin":
        resolve_paths = [
            "/Applications/DaVinci Resolve/DaVinci Resolve.app",
            "/Applications/DaVinci Resolve Studio/DaVinci Resolve Studio.app",
        ]
    elif system == "Windows":
        resolve_paths = [
            "C:\\Program Files\\Blackmagic Design\\DaVinci Resolve\\Resolve.exe",
            "C:\\Program Files\\Blackmagic Design\\DaVinci Resolve Studio\\Resolve.exe",
        ]
    else:
        return False
    
    for path in resolve_paths:
        if os.path.exists(path):
            print_success(f"Found DaVinci Resolve at: {path}")
            return True
    
    print_error("DaVinci Resolve not found")
    print_info("Please install DaVinci Resolve from:")
    print_info("https://www.blackmagicdesign.com/products/davinciresolve/")
    return False


def check_python_installation():
    """Check if Python is installed and accessible."""
    print_info("Checking for Python installation...")
    
    try:
        # Check Python version
        result = subprocess.run(
            ["python3", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        version = result.stdout.strip()
        print_success(f"Found {version}")
        
        # Get Python executable path
        result = subprocess.run(
            ["which", "python3"],
            capture_output=True,
            text=True,
            check=True
        )
        python_path = result.stdout.strip()
        print_success(f"Python executable: {python_path}")
        
        # Check if Python version is 3.8+
        version_check = subprocess.run(
            ["python3", "-c", "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"],
            capture_output=True
        )
        
        if version_check.returncode != 0:
            print_error("Python 3.8 or higher is required.")
            return False
        
        return True
        
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_error("Python 3 is not installed or not in PATH.")
        print_info("Please install Python from: https://www.python.org/downloads/")
        return False


def check_pip_installation():
    """Check if pip is installed."""
    print_info("Checking for pip...")
    
    try:
        result = subprocess.run(
            ["python3", "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        print_success(f"Found pip: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError:
        print_error("pip is not installed.")
        print_info("Installing pip...")
        try:
            subprocess.run(
                ["python3", "-m", "ensurepip", "--default-pip"],
                check=True
            )
            print_success("pip installed successfully.")
            return True
        except subprocess.CalledProcessError:
            print_error("Failed to install pip.")
            return False


def get_dependencies_from_pyproject():
    """Read dependencies from pyproject.toml."""
    script_dir = Path(__file__).parent.absolute()
    pyproject_path = script_dir / "frontend/plugin/pyproject.toml"
    
    if not pyproject_path.exists():
        print_warning(f"pyproject.toml not found at {pyproject_path}")
        # Fallback to hardcoded dependencies
        return [
            "pyqt6>=6.10.0",
            "requests>=2.31.0",
            "watchdog>=3.0.0",
        ]
    
    # Try to parse pyproject.toml
    if tomllib is None:
        print_warning("TOML parser not available, using fallback dependencies")
        return [
            "pyqt6>=6.10.0",
            "requests>=2.31.0",
            "watchdog>=3.0.0",
        ]
    
    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
            dependencies = data.get("project", {}).get("dependencies", [])
            if dependencies:
                print_success(f"Loaded {len(dependencies)} dependencies from pyproject.toml")
                return dependencies
            else:
                print_warning("No dependencies found in pyproject.toml")
                return []
    except Exception as e:
        print_error(f"Failed to read pyproject.toml: {e}")
        return [
            "pyqt6>=6.10.0",
            "requests>=2.31.0",
            "watchdog>=3.0.0",
        ]

def install_dependencies():
    """Install required Python packages."""
    print_info("Installing Python dependencies...")
    
    dependencies = get_dependencies_from_pyproject()
    
    if not dependencies:
        print_warning("No dependencies to install.")
        return True
    
    for dep in dependencies:
        print_info(f"Installing {dep}...")
        try:
            subprocess.run(
                ["python3", "-m", "pip", "install", "--upgrade", dep],
                check=True,
                capture_output=True
            )
            print_success(f"Installed {dep}")
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to install {dep}")
            print_error(f"Error: {e.stderr.decode() if e.stderr else 'Unknown error'}")
            return False
    
    print_success("All dependencies installed successfully.")
    return True


def get_resolve_plugin_directory():
    """Get the DaVinci Resolve plugin directory path."""
    system = platform.system()
    
    if system == "Darwin":
        # macOS paths
        user_plugin_dir = Path.home() / "Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
        system_plugin_dir = Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility")
    elif system == "Windows":
        # Windows paths
        appdata = os.getenv("APPDATA")
        programdata = os.getenv("PROGRAMDATA")
        user_plugin_dir = Path(appdata) / "Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts/Utility"
        system_plugin_dir = Path(programdata) / "Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
    else:
        return Path.home() / "ClipABit"  # Fallback
    
    # Try user directory first
    if user_plugin_dir.exists() or not system_plugin_dir.exists():
        return user_plugin_dir
    
    return system_plugin_dir


def copy_plugin_files():
    """Copy the plugin files to the DaVinci Resolve plugin directory."""
    print_info("Installing ClipABit plugin...")
    
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.absolute()
    plugin_source = script_dir / "frontend/plugin"
    
    if not plugin_source.exists():
        print_error(f"Plugin source directory not found: {plugin_source}")
        return False
    
    # Get target directory
    plugin_dir = get_resolve_plugin_directory()
    plugin_target = plugin_dir / "ClipABit"
    
    print_info(f"Source: {plugin_source}")
    print_info(f"Target: {plugin_target}")
    
    # Create target directory if it doesn't exist
    try:
        plugin_dir.mkdir(parents=True, exist_ok=True)
        print_success(f"Plugin directory ready: {plugin_dir}")
    except Exception as e:
        print_error(f"Failed to create plugin directory: {e}")
        return False
    
    # Remove existing installation if present
    if plugin_target.exists():
        print_warning("Existing ClipABit installation found. Removing...")
        try:
            shutil.rmtree(plugin_target)
            print_success("Removed existing installation.")
        except Exception as e:
            print_error(f"Failed to remove existing installation: {e}")
            return False
    
    # Copy plugin files
    try:
        shutil.copytree(plugin_source, plugin_target)
        print_success(f"Plugin files copied to: {plugin_target}")
        
        # Make the main plugin file executable
        main_plugin = plugin_target / "clipabit.py"
        if main_plugin.exists():
            os.chmod(main_plugin, 0o755)
            print_success("Plugin file permissions set.")
        
        return True
    except Exception as e:
        print_error(f"Failed to copy plugin files: {e}")
        return False


def verify_installation():
    """Verify that the installation was successful."""
    print_info("Verifying installation...")
    
    plugin_dir = get_resolve_plugin_directory()
    plugin_path = plugin_dir / "ClipABit/clipabit.py"
    
    if not plugin_path.exists():
        print_error("Plugin file not found after installation.")
        return False
    
    print_success("Plugin file verified.")
    
    # Check if dependencies are importable
    print_info("Checking dependencies...")
    try:
        subprocess.run(
            ["python3", "-c", "import PyQt6, requests, watchdog"],
            check=True,
            capture_output=True
        )
        print_success("All dependencies are accessible.")
        return True
    except subprocess.CalledProcessError:
        print_error("Some dependencies are not accessible.")
        return False


def print_Utilityletion_message():
    """Print installation Utilityletion message."""
    print_header("Installation Utilitylete!")
    print_success("ClipABit plugin has been installed successfully.")
    print()
    print_info("To use the plugin in DaVinci Resolve:")
    print("  1. Open DaVinci Resolve")
    print("  2. Go to the Fusion page")
    print("  3. Open the Script menu")
    print("  4. Select 'Utility' → 'ClipABit' → 'clipabit'")
    print()
    print_info("For support, visit: https://github.com/yourusername/clipabit")
    print()


def main():
    """Main installation function."""
    print_header("ClipABit Plugin Installer")
    
    # Check if running on a supported platform
    if not check_platform():
        sys.exit(1)
    
    # Check DaVinci Resolve installation
    if not check_davinci_resolve():
        print_error("Installation aborted: DaVinci Resolve not found.")
        sys.exit(1)
    
    # Check Python installation
    if not check_python_installation():
        print_error("Installation aborted: Python not found.")
        sys.exit(1)
    
    # Check pip installation
    if not check_pip_installation():
        print_error("Installation aborted: pip not available.")
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print_error("Installation aborted: Failed to install dependencies.")
        sys.exit(1)
    
    # Copy plugin files
    if not copy_plugin_files():
        print_error("Installation aborted: Failed to copy plugin files.")
        sys.exit(1)
    
    # Verify installation
    if not verify_installation():
        print_warning("Installation Utilityleted with warnings.")
        sys.exit(0)
    
    # Print Utilityletion message
    print_Utilityletion_message()
    sys.exit(0)


if __name__ == "__main__":
    main()
