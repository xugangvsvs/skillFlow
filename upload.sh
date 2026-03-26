#!/bin/bash

# --- 远程环境配置 ---
USER="gaxu"
HOST="10.181.49.72"
REMOTE_DIR="/var/fpwork/gaxu/skillFlow"
# ------------------

echo "[*] 正在同步核心代码与技能库到 EECloud..."

# 1. 确保远程目录存在
ssh $USER@$HOST "mkdir -p $REMOTE_DIR"

# 2. 精准同步白名单文件：
# -r ./src    : 同步源码目录
# ./SKILL.md  : 同步 AI 技能库
# ./*.py      : 同步根目录下所有 Python 脚本（含 test_api.py）
# ./*.sh      : 同步 Shell 脚本本身
scp -r ./src ./SKILL.md ./*.py ./*.sh $USER@$HOST:$REMOTE_DIR/

echo "-----------------------------------------------"
echo "[+] 同步完成！"
echo "[*] 提示：请记得手动清理远程的 node.exe 及相关缓存文件。"
echo "[*] 下一步：在 EECloud 运行 python3 test_api.py"
echo "-----------------------------------------------"
