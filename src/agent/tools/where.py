import platform
import subprocess

os_type = platform.system().lower()

def _where() -> str:
    if os_type == "windows":
        return subprocess.run('cd', shell=True, capture_output=True, text=True, check=True).stdout.strip()
    else:
        return subprocess.run('pwd', shell=True, capture_output=True, text=True, check=True).stdout.strip()


where = {
    "type": "function",
    "function": {
        "name": "where",
        "description": "Get the current working directory of the agent.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    "call": _where,
}