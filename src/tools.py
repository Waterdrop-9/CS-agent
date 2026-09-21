from pathlib import Path
import subprocess

TOOL_DEFINITIONS = [
    {
        "name": "list_files",
        "description": "List files and directories at the workspace root.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "read_file",
        "description": "Read a UTF-8 text file inside the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File path relative to the workspace.",
                },
            },
            "required": ["file_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "write_file",
        "description": "Write UTF-8 text to a file inside the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File path relative to the workspace.",
                },
                "content": {
                    "type": "string",
                    "description": "Complete new content of the file.",
                },
            },
            "required": ["file_path", "content"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_command",
        "description": "Run a shell command in the workspace directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to run in the workspace.",
                },
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    },
]


def resolve_path(workspace: Path, file_path: str) -> Path:
    """ 将相对路径解析为workspace下的绝对路径 """
    # Validate inputs
    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("file_path must be a non-empty string")
    relative_path = Path(file_path)
    if relative_path.is_absolute():
        raise ValueError("file_path must be a relative path")

    root = workspace.resolve()
    target = (root / relative_path).resolve()

    if not target.is_relative_to(root):
        raise ValueError(f"Resolved path {target} is outside of the workspace {root}")

    return target

def list_files(workspace: Path) -> str:
    """列出工作区第一层的文件与目录"""
    entries = []
    for path in sorted(workspace.iterdir()):
        suffix = "/" if path.is_dir() else ""
        entries.append(f"{path.name}{suffix}")
    return "\n".join(entries) or "(empty directory)"

def read_file(workspace: Path, file_path: str) -> str:
    """读取工作区下的文件内容"""
    target = resolve_path(workspace, file_path)
    if not target.is_file():
        raise FileNotFoundError(f"{target} is not a file")
    return target.read_text(encoding="utf-8")

def execute_tools(workspace: Path, call: dict) -> dict:
    """执行一个工具调用，返回统一结果
    返回格式：
    {
        "tool_call_id": str,
        "ok": bool,
        "content": str
    }
    """
    # 模型边界已检查 id 和 name；本层只检查工具名称和参数。
    tool_call_id = call["id"]
    tool_name = call["name"]

    # 错误处理
    try:
        args = call.get("arguments", {})

        if not isinstance(args, dict):
            raise ValueError("arguments must be a dictionary")

        if tool_name == "list_files":
            content = list_files(workspace)
        elif tool_name == "read_file":
            content = read_file(workspace, args.get("file_path", ""))
        elif tool_name == "write_file":
            content = write_file(workspace, args.get("file_path", ""), args.get("content", ""))
        elif tool_name == "run_command":
            ok, content = run_command(workspace, args.get("command", ""))
            return {
                "tool_call_id": tool_call_id,
                "ok": ok,
                "content": content,
            }
        else:
            raise ValueError(f"Unknown tool name: {tool_name}")

    except (ValueError, OSError) as e:
        return {
            "tool_call_id": tool_call_id,
            "ok": False,
            "content": str(e),
        }
    # 正确返回
    return {
        "tool_call_id": tool_call_id,
        "ok": True,
        "content": content,
    }

def write_file(workspace: Path, file_path: str, content: str) -> str:
    """写入工作区下的 UTF-8 文本文件。"""
    if not isinstance(content, str):
        raise ValueError("content must be a string")

    target = resolve_path(workspace, file_path)
    target.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to {file_path}"


def run_command(workspace: Path, command: str) -> tuple[bool, str]:
    """在 workspace 中执行命令，并返回是否成功及可读结果。"""
    if not isinstance(command, str) or not command.strip():
        raise ValueError("command must be a non-empty string")

    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or "") + (error.stderr or "")
        return False, f"command timed out after 30 seconds\n{output}"

    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode == 0, (
        f"exit_code={completed.returncode}\n{output}"
    )
