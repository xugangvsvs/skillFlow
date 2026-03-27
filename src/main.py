import os
from src.scanner import SkillScanner, match_skill
from src.executor import CopilotExecutor

def run_app():
    # Adjust path based on project structure
    repo_path = "./dev-skills"
    scanner = SkillScanner(repo_path)
    executor = CopilotExecutor()

    print("\n" + "="*50)
    print("   Nokia AI SkillFlow: 40+ Skills Loaded   ")
    print("="*50)
    
    skills = scanner.scan()
    print(f"[*] System status: Successfully loaded {len(skills)} skills.")

    while True:
        try:
            user_input = input("\n[User] Enter log or analysis request (q to quit): ").strip()
            
            if user_input.lower() == 'q':
                break
            if not user_input:
                continue

            # Matching logic (case-insensitive, search in name and description)
            matched = match_skill(skills, user_input)

            if matched:
                print(f"[*] Matched skill: [{matched['name']}]")
                print(f"[*] Calling Nokia LLM for analysis...")
                
                # Combine matched skill metadata with user input as context for AI
                prompt = f"Using this skill spec:\n{matched}\n\nAnalyze this user query: {user_input}"
                
                response = executor.ask_ai(prompt)
                print(f"\n[AI Analysis Suggestion]:\n{response}")
            else:
                print("[!] No matching skills found. Try keywords like: ims2, SIP, 403")

        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    run_app()
