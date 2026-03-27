from flask import Flask, jsonify, request, Response
try:
    from src.scanner import SkillScanner
    from src.executor import CopilotExecutor
except ModuleNotFoundError:
    # Allow running directly as 'python src/app.py' from project root
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.scanner import SkillScanner
    from src.executor import CopilotExecutor
import json


def create_app(skill_path: str = "./dev-skills") -> Flask:
    """
    Factory function to create and configure the Flask application.
    
    Args:
        skill_path: Path to the dev-skills directory for skill discovery.
    
    Returns:
        Configured Flask app instance.
    """
    app = Flask(__name__)
    
    # Initialize scanner and executor at app startup
    scanner = SkillScanner(skill_path)
    skills = scanner.scan()
    executor = CopilotExecutor()
    
    # Helper: find skill by name
    def find_skill_by_name(name: str):
        """Find a skill in the loaded skills list by name."""
        for skill in skills:
            if skill.get("name") == name:
                return skill
        return None
    
    @app.route("/api/skills", methods=["GET"])
    def get_skills():
        """
        Endpoint to fetch all available skills.
        
        Returns:
            JSON list of skills with basic metadata (name, description, id).
        """
        skill_list = [
            {
                "name": s.get("name"),
                "description": s.get("description"),
                "id": s.get("id"),
            }
            for s in skills
        ]
        return jsonify(skill_list), 200
    
    @app.route("/api/analyze", methods=["POST"])
    def analyze():
        """
        Endpoint to analyze user input using a selected skill.
        
        Expected payload:
            {
                "skill_name": "analyze-ims2",
                "user_input": "text to analyze"
            }
        
        Returns:
            JSON with analysis result or error message.
        """
        data = request.get_json()
        
        # Validate payload
        if not data:
            return jsonify({"error": "Missing JSON payload"}), 400
        
        skill_name = data.get("skill_name")
        user_input = data.get("user_input")
        
        if not skill_name or not user_input:
            return jsonify({"error": "Missing required fields: skill_name, user_input"}), 400
        
        # Find the skill
        skill = find_skill_by_name(skill_name)
        if not skill:
            return jsonify({"error": f"Skill '{skill_name}' not found"}), 404
        
        # Build prompt: combine skill metadata with user input
        skill_content = skill.get("full_content", "")
        prompt = f"Using this skill spec:\n{skill_content}\n\nAnalyze this user query: {user_input}"
        
        # Call LLM executor
        result = executor.ask_ai(prompt)
        
        return jsonify({"result": result}), 200
    
    @app.route("/api/analyze/stream", methods=["POST"])
    def analyze_stream():
        """
        Endpoint to analyze user input with Server-Sent Events (SSE) streaming.
        Streams the AI response in real-time to the client.
        
        Expected payload:
            {
                "skill_name": "analyze-ims2",
                "user_input": "text to analyze"
            }
        
        Returns:
            Streamed response chunks as SSE.
        """
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Missing JSON payload"}), 400
        
        skill_name = data.get("skill_name")
        user_input = data.get("user_input")
        
        if not skill_name or not user_input:
            return jsonify({"error": "Missing required fields: skill_name, user_input"}), 400
        
        skill = find_skill_by_name(skill_name)
        if not skill:
            return jsonify({"error": f"Skill '{skill_name}' not found"}), 404
        
        # Build prompt
        skill_content = skill.get("full_content", "")
        prompt = f"Using this skill spec:\n{skill_content}\n\nAnalyze this user query: {user_input}"
        
        # Call LLM executor
        # Note: For now, we'll return the full result in chunks
        # Future: implement true streaming from the LLM API
        result = executor.ask_ai(prompt)
        
        def generate():
            """Generator function for SSE."""
            yield f"data: {json.dumps({'chunk': result})}\n\n"
        
        return Response(generate(), mimetype="text/event-stream"), 200
    
    return app


if __name__ == "__main__":
    import sys
    import os
    # Ensure project root is in sys.path when run directly as 'python src/app.py'
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
