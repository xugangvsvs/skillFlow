#!/usr/bin/env python3
"""
Integration test: verify Flask app and API endpoints work.
Run: python test_integration.py
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

def test_integration():
    print("\n" + "="*60)
    print("INTEGRATION TEST: SkillFlow Local Verification")
    print("="*60)
    
    print("\n[1/3] Verifying imports...")
    try:
        from src.app import create_app
        from src.scanner import SkillScanner
        print("      ✓ Can import app and scanner")
    except ImportError as e:
        print(f"      ✗ Import failed: {e}")
        return False
    
    print("\n[2/3] Creating Flask test client...")
    try:
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        print("      ✓ Flask app created and ready")
    except Exception as e:
        print(f"      ✗ Flask init failed: {e}")
        return False
    
    print("\n[3/3] Testing endpoints...")
    
    # Test 1: GET /api/skills
    print("      → GET /api/skills")
    try:
        resp = client.get("/api/skills")
        if resp.status_code == 200:
            skills = resp.get_json()
            if isinstance(skills, list) and len(skills) > 0:
                first = skills[0]
                inputs_count = len(first.get("inputs", []))
                print(f"        ✓ Got {len(skills)} skill(s), example '{first['name']}' with {inputs_count} input(s)")
            else:
                print("        ⚠ Empty skills list (but endpoint works)")
        else:
            print(f"        ✗ Expected 200, got {resp.status_code}")
            return False
    except Exception as e:
        print(f"        ✗ Error: {e}")
        return False
    
    # Test 2: POST /api/analyze with mock LLM
    print("      → POST /api/analyze (mocked LLM)")
    try:
        with patch("src.app.CopilotExecutor.ask_ai", return_value="Test response"):
            resp = client.post("/api/analyze", json={
                "skill_name": "analyze-ims2",
                "user_input": "test query"
            })
            if resp.status_code == 200:
                result = resp.get_json()
                if "result" in result and "mode" in result:
                    print(f"        ✓ Got response (mode={result['mode']})")
                else:
                    print(f"        ✗ Missing fields in response")
                    return False
            else:
                print(f"        ✗ Expected 200, got {resp.status_code}")
                return False
    except Exception as e:
        print(f"        ✗ Error: {e}")
        return False
    
    # Test 3: GET / (web UI)
    print("      → GET / (Web UI)")
    try:
        resp = client.get("/")
        if resp.status_code == 200 and "SkillFlow" in resp.get_data(as_text=True):
            print("        ✓ Web UI accessible")
        else:
            print(f"        ✗ Expected 200 with SkillFlow content")
            return False
    except Exception as e:
        print(f"        ✗ Error: {e}")
        return False
    
    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60)
    print("\nNext steps:")
    print("  • Run web UI locally: python -m src.app")
    print("  • Deploy with Docker: docker-compose up --build")
    print("  • See README.md for full documentation")
    print("\n")
    return True

if __name__ == "__main__":
    success = test_integration()
    sys.exit(0 if success else 1)
