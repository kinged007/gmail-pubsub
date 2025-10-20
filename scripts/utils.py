import os
import subprocess
import sys
import shlex
import json
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

GCLOUD_PATH = None

def find_gcloud_executable():
    """Find the gcloud executable on the system."""
    global GCLOUD_PATH
    if GCLOUD_PATH:
        return GCLOUD_PATH

    # Common gcloud installation paths on Windows
    common_paths = [
        "gcloud",  # If it's in PATH
        r"C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
        r"C:\Program Files\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
        r"C:\Users\{}\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd".format(os.environ.get('USERNAME', '')),
        r"C:\google-cloud-sdk\bin\gcloud.cmd",
    ]

    for path in common_paths:
        try:
            # Test if the executable exists and works
            result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"✓ Found gcloud at: {path}")
                GCLOUD_PATH = path
                return path
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue

    print("❌ Could not find gcloud executable. Please ensure Google Cloud SDK is installed.")
    print("Download from: https://cloud.google.com/sdk/docs/install")
    return None


def run_command(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    print(f"Running: {cmd}")

    # Set up environment
    env = os.environ.copy()
    env['CLOUDSDK_PYTHON'] = sys.executable

    # Handle gcloud commands specially on Windows
    if cmd.startswith('gcloud ') or 'gcloud.cmd' in cmd:
        gcloud_path = find_gcloud_executable()
        if not gcloud_path:
            print("❌ Cannot execute gcloud commands - gcloud not found")
            sys.exit(1)

        # For gcloud commands that already contain the full path, use shell execution
        if 'gcloud.cmd' in cmd and os.name == 'nt':
            # Use shell execution for Windows with full path, but quote the executable path
            # Find the end of the .cmd file and split there
            cmd_end = cmd.find('gcloud.cmd') + len('gcloud.cmd')
            executable = cmd[:cmd_end]
            args = cmd[cmd_end:].strip()
            if args:
                quoted_cmd = f'"{executable}" {args}'
            else:
                quoted_cmd = f'"{executable}"'
            result = subprocess.run(quoted_cmd, shell=True, capture_output=True, text=True, env=env)
        else:
            # Use shlex for Unix-like systems or simple gcloud commands
            cmd_parts = shlex.split(cmd)
            # Only replace the first part if it's just "gcloud", not a full path
            if cmd_parts[0] == 'gcloud':
                cmd_parts[0] = gcloud_path

            # Use subprocess with list of arguments for better reliability
            result = subprocess.run(cmd_parts, capture_output=True, text=True, env=env)
    else:
        # For non-gcloud commands, use shell execution
        if os.name == 'nt':  # Windows
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                                  env=env, executable='cmd.exe')
        else:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)

    if check and result.returncode != 0:
        print(f"Error running command: {cmd}")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        sys.exit(1)

    return result


def clean_json_value(value: str) -> str:
    """Clean JSON value to be single-line for env files."""
    if not value:
        return value

    # Check if value looks like JSON (starts with { and ends with })
    stripped = value.strip()
    if stripped.startswith('{') and stripped.endswith('}'):
        try:
            # Parse and reformat as compact JSON
            parsed = json.loads(stripped)
            return json.dumps(parsed, separators=(',', ':'))
        except (json.JSONDecodeError, ValueError):
            # If it's not valid JSON, return as-is
            pass

    return value


def create_env_file():
    """Create .env file from .env.example if it doesn't exist."""
    env_file = Path(project_root / '.env')
    env_example_file = Path(project_root / '.env.example')

    if not env_file.exists():
        if env_example_file.exists():
            import shutil
            shutil.copy(env_example_file, env_file)
            print("✓ Created .env file from .env.example")
        else:
            # Create basic .env file
            with open(env_file, 'w') as f:
                f.write("# Environment variables for Gmail Pub/Sub project\n")
                f.write("LOG_LEVEL=INFO\n")
                f.write("GMAIL_WATCH_LABELS=INBOX\n")
            print("✓ Created basic .env file")
        
        # Place a simple header at end of the file
        with open(env_file, 'a') as f:
            f.write("\n# Vars for Gmail Pub/Sub project\n")
    else:
        print("✓ .env file already exists")


def update_env_file(key: str, value: str):
    """Update or add a key-value pair in the .env file."""
    env_file = Path(project_root / '.env')

    # Read existing content
    lines = []
    if env_file.exists():
        with open(env_file, 'r') as f:
            lines = f.readlines()

    # Check if key already exists
    key_exists = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f'{key}='):
            lines[i] = f'{key}={clean_json_value(value)}\n'
            key_exists = True
            break

    # If key doesn't exist, add it
    if not key_exists:
        lines.append(f'{key}={clean_json_value(value)}\n')

    # Write back to file
    with open(env_file, 'w') as f:
        f.writelines(lines)

    print(f"✓ Updated {key} in .env file")


def clear_mapped_env_variables():
    """Clear all environment variables defined in the env_var_map from .env file."""
    from src.config import env_var_map

    env_file = Path(project_root / '.env')
    if not env_file.exists():
        print("✓ No .env file found, nothing to clear")
        return

    # Get all environment variable names from the map
    mapped_env_vars = set(env_var_map.values())

    # Variables to preserve during reset (custom user configuration)
    preserve_vars = {
        'LOG_LEVEL',
        'GMAIL_WATCH_LABELS',
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_CHAT_ID',
        # Add other custom variables that should be preserved
    }

    # Read existing content
    lines = []
    with open(env_file, 'r') as f:
        lines = f.readlines()

    # Filter out lines that start with mapped environment variables
    filtered_lines = []
    removed_vars = []

    for line in lines:
        stripped_line = line.strip()
        # Skip empty lines and comments
        if not stripped_line or stripped_line.startswith('#'):
            filtered_lines.append(line)
            continue

        # Check if this line defines a mapped environment variable
        is_mapped_var = False
        var_name = None
        for env_var in mapped_env_vars:
            if stripped_line.startswith(f'{env_var}='):
                is_mapped_var = True
                var_name = env_var
                break

        # Keep the line if it's not a mapped variable OR if it's in preserve list
        if not is_mapped_var or (var_name and var_name in preserve_vars):
            filtered_lines.append(line)
        else:
            # Only add to removed list if actually removing
            if var_name:
                removed_vars.append(var_name)

    # Write back filtered content
    with open(env_file, 'w') as f:
        f.writelines(filtered_lines)

    if removed_vars:
        print(f"✓ Cleared {len(removed_vars)} mapped environment variables from .env file:")
        for var in sorted(removed_vars):
            print(f"  - {var}")
    else:
        print("✓ No mapped environment variables found in .env file")
