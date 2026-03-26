import requests
import json
import uuid

# 从环境变量读取 token，不要硬编码在代码里
import os
token = os.environ.get("GITHUB_COPILOT_TOKEN", "")

url = "https://api.githubcopilot.com/chat/completions"

# 这里的 Header 是关键，必须精准模拟 VS Code
headers = {
    "Authorization": f"Bearer {token}",
    "X-Request-Id": str(uuid.uuid4()),
    "X-Github-Api-Version": "2023-07-07",
    "Vscode-Sessionid": str(uuid.uuid4()),
    "Vscode-Machineid": "some_random_hex_string_12345", # 随便填个数
    "Editor-Version": "vscode/1.85.1",
    "Editor-Plugin-Version": "copilot-chat/0.11.1",
    "User-Agent": "GitHubCopilotChat/0.11.1",
    "Accept": "*/*",
    "Content-Type": "application/json",
}

data = {
    "messages": [
        {"role": "user", "content": "Hello! Reply with 'Connection Success' if you hear me."}
    ],
    "model": "gpt-4", # 尝试改成 gpt-3.5-turbo 如果 gpt-4 报错
    "stream": False
}

print("[*] 正在尝试深度伪装请求...")
try:
    response = requests.post(url, headers=headers, json=data, timeout=15)
    print(f"[+] 状态码: {response.status_code}")
    if response.status_code == 200:
        print("[+] 回复内容:", response.json()['choices'][0]['message']['content'])
    else:
        print("[-] 错误详情:", response.text)
except Exception as e:
    print(f"[-] 网络错误: {e}")
