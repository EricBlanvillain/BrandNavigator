#!/bin/bash

# Get the directory where the script is located (should be the project root)
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# Define the path to the virtual environment directory (assuming it's one level up)
VENV_DIR="$SCRIPT_DIR/../venv"

# Check if the virtual environment activation script exists
if [ -f "$VENV_DIR/bin/activate" ]; then
    echo "Activating virtual environment from $VENV_DIR..."
    source "$VENV_DIR/bin/activate"
    echo "Virtual environment activated."
else
    echo "Error: Virtual environment not found at $VENV_DIR" >&2
    echo "Please ensure 'venv' directory exists one level above the project root." >&2
    exit 1
fi

# Navigate to the script's directory (project root) just in case
cd "$SCRIPT_DIR" || exit

# Load environment variables from .env (flask run does this automatically)
echo "Starting Flask development server (using .env for configuration)..."

# Run the Flask development server (port 5001 as used before)
# FLASK_APP=app and FLASK_ENV=development should be picked up from .env in this directory
flask run --port=5001

# Deactivate venv when script exits (optional, usually happens automatically on script end)
# echo "Deactivating virtual environment..."
# deactivate

echo "Flask server stopped."
