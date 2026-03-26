import subprocess
import shutil
import os

class CopilotExecutor:
    def __init__(self):
        # 1. 优先寻找新版 CLI 命令
        self.cmd_name = "copilot-assistant" 
        if not shutil.which(self.cmd_name):
            # 兼容性备选（某些安装方式下名为 github-copilot-cli）
            self.cmd_name = "github-copilot-cli"

    def ask_ai(self, prompt):
        # 构造新版命令格式
        # copilot-assistant explain "..."
        cmd = [self.cmd_name, "explain", prompt]
        
        try:
            # 增加环境变量注入，确保 Node v24 的路径在里面
            current_env = os.environ.copy()
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                shell=True, 
                encoding='utf-8',
                env=current_env,
                timeout=40
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                # 如果没安装，给出具体的安装指令
                if "not found" in result.stderr.lower() or "不是内部或外部命令" in result.stderr:
                    return "ERROR: 未安装新版 CLI。请运行: npm install -g @githubnext/github-copilot-cli"
                return f"AI_BACKEND_ERROR: {result.stderr}"
                
        except Exception as e:
            return f"SYSTEM_ERROR: {str(e)}"
