import yaml
from pathlib import Path

class SkillScanner:
    def __init__(self, repo_path):
        self.repo_path = Path(repo_path)

    def scan(self):
        skills = []
        for md_file in self.repo_path.glob("**/SKILL.md"):
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.startswith("---"):
                    parts = content.split("---")
                    if len(parts) >= 3:
                        data = yaml.safe_load(parts[1])
                        if data:
                            data['abs_path'] = str(md_file)
                            data['full_content'] = content
                            skills.append(data)
        return skills

def match_skill(skills, user_input):
    """
    极简、健壮的匹配引擎
    """
    if not user_input:
        return None
    
    # 1. 统一转小写
    query = user_input.lower()
    
    for skill in skills:
        # --- 维度 A: Keywords (最优先) ---
        # 使用 or [] 确保哪怕 YAML 没填内容，keywords 也是个列表
        kws = skill.get('keywords') or []
        if isinstance(kws, str):
            kws = [kws]
        
        # 只要有一个 keyword 被包含在用户输入中
        if any(str(k).lower() in query for k in kws if k):
            return skill

        # --- 维度 B: Description (次优先) ---
        desc = skill.get('description') or ""
        if query in str(desc).lower():
            return skill

        # --- 维度 C: Name (保底) ---
        name = skill.get('name') or ""
        if query in str(name).lower():
            return skill
            
    return None
