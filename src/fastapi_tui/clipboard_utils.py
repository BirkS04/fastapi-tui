"""
Cross-platform clipboard utilities with OSC52 support for SSH sessions.
Works on Linux, macOS, and Windows.
"""

import platform
import base64
import sys


def copy_to_clipboard(text: str) -> tuple[bool, str]:
    """
    Copy text to clipboard using the best available method.
    
    Returns:
        tuple[bool, str]: (success, error_message)
    """
    # Try OSC52 first (works over SSH and locally for compatible terminals)
    if _try_osc52(text):
        return True, ""
    
    # Fallback to platform-specific methods
    system = platform.system()
    
    if system == "Windows":
        return _copy_windows(text)
    else:  # Linux, macOS
        return _copy_unix(text)


def _try_osc52(text: str) -> bool:
    """
    Try to copy using OSC52 escape sequence.
    This works in most modern terminals, including over SSH.
    """
    try:
        encoded = base64.b64encode(text.encode()).decode()
        osc52 = f"\033]52;c;{encoded}\007"
        
        # Try to write directly to terminal
        if platform.system() == "Windows":
            try:
                with open('CON', 'w', encoding='utf-8') as tty:
                    tty.write(osc52)
                    tty.flush()
                    return True
            except:
                pass
        else:
            try:
                with open('/dev/tty', 'w') as tty:
                    tty.write(osc52)
                    tty.flush()
                    return True
            except:
                pass
        
        return False
    except Exception:
        return False


def _copy_windows(text: str) -> tuple[bool, str]:
    """Copy to clipboard on Windows."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return True, ""
    except ImportError:
        return False, "pyperclip not installed. Install with: pip install pyperclip"
    except Exception as e:
        return False, f"Copy failed: {e}"


def _copy_unix(text: str) -> tuple[bool, str]:
    """Copy to clipboard on Linux/macOS."""
    # Try pyperclip first
    try:
        import pyperclip
        pyperclip.copy(text)
        return True, ""
    except ImportError:
        pass
    except Exception:
        pass
    
    # Fallback to xclip/xsel on Linux
    if platform.system() == "Linux":
        import subprocess
        
        # Try xclip
        try:
            subprocess.run(
                ['xclip', '-selection', 'clipboard'],
                input=text.encode(),
                check=True,
                timeout=1
            )
            return True, ""
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
        
        # Try xsel
        try:
            subprocess.run(
                ['xsel', '--clipboard', '--input'],
                input=text.encode(),
                check=True,
                timeout=1
            )
            return True, ""
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
    
    # Fallback to pbcopy on macOS
    if platform.system() == "Darwin":
        import subprocess
        try:
            subprocess.run(
                ['pbcopy'],
                input=text.encode(),
                check=True,
                timeout=1
            )
            return True, ""
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
    
    return False, "No clipboard method available. Install pyperclip or xclip/xsel"


# Convenience function for Textual widgets
def copy_and_notify(widget, text: str, success_msg: str = "Copied to clipboard!"):
    """
    Copy text and show notification in Textual widget.
    
    Args:
        widget: Textual widget with notify() method
        text: Text to copy
        success_msg: Success message to show
    """
    success, error = copy_to_clipboard(text)
    
    if success:
        widget.notify(success_msg, title="✓ Copied", severity="information")
    else:
        widget.notify(
            f"Copy failed: {error}",
            title="✗ Error",
            severity="error"
        )