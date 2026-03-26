import os
from src.scanner import SkillScanner, match_skill
from src.executor import CopilotExecutor

def run_app():
    # 路径根据你的项目结构调整
    repo_path = "./dev-skills" 
    scanner = SkillScanner(repo_path)
    executor = CopilotExecutor()

    print("\n" + "="*50)
    print("   Nokia AI SkillFlow: 40+ Skills Loaded   ")
    print("="*50)
    
    skills = scanner.scan()
    print(f"[*] 系统状态: 已成功加载 {len(skills)} 个技能。")

    while True:
        try:
            user_input = input("\n[User] 输入 Log 或分析需求 (q 退出): ").strip()
            
            if user_input.lower() == 'q':
                break
            if not user_input:
                continue

            # 匹配逻辑 (不区分大小写，搜索 name 和 description)
            matched = match_skill(skills, user_input)

            if matched:
                print(f"[*] 命中技能: [{matched['name']}]")
                print(f"[*] 正在调用 Copilot 进行分析...")
                
                # 将匹配到的整个 SKILL.md 内容作为上下文发给 AI
                # 这样 AI 就能根据你拷贝的那个 ims2 规范来回答
                prompt = f"Using this skill spec:\n{matched}\n\nAnalyze this user query: {user_input}"
                
                response = executor.ask_ai(prompt)
                print(f"\n[AI 分析建议]:\n{response}")
            else:
                print("[!] 未匹配到相关技能。您可以尝试输入关键词，如: ims2, SIP, 403")

        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    run_app()
