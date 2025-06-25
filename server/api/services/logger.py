from rich.theme import Theme
from rich.console import Console

# Custom theme for the console output
custom_theme = Theme(
    {
        "info": "dim cyan",
        "warning": "magenta",
        "error": "bold red",
        "success": "bold green",
        "debug": "dim white",
        "log.time": "italic dim blue",  # Default for log() timestamp
        "log.level": "bold",  # Default for log() level
    }
)

# Create a console instance with the custom theme
console = Console(theme=custom_theme, record=True, log_time_format="%H:%M:%S.%f")
