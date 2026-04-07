import requests
import json
import uuid

# Read token from the environment; do not hard-code secrets.
import os
token = os.environ.get("GITHUB_COPILOT_TOKEN", "")

url = "https://api.githubcopilot.com/chat/completions"

# Headers must mimic VS Code / Copilot client expectations.
headers = {
    "Authorization": f"Bearer {token}",
    "X-Request-Id": str(uuid.uuid4()),
    "X-Github-Api-Version": "2023-07-07",
    "Vscode-Sessionid": str(uuid.uuid4()),
    "Vscode-Machineid": "some_random_hex_string_12345",
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
    "model": "gpt-4",
    "stream": False
}

print("[*] Sending Copilot-style request...")
try:
    response = requests.post(url, headers=headers, json=data, timeout=15)
    print(f"[+] HTTP status: {response.status_code}")
    if response.status_code == 200:
        print("[+] Reply:", response.json()['choices'][0]['message']['content'])
    else:
        print("[-] Error body:", response.text)
except Exception as e:
    print(f"[-] Request failed: {e}")
