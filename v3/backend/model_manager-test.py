"""
model_manager-test.py
Tests all models registered in model_manager.py
Handles local and cloud models safely, skipping cloud models
if there are API or quota issues.
"""
import sys
import os

# Add the modules directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app/modules"))

from model_manager import list_models, get_default_model, generate_response

def test_models():
    models = list_models()
    print("Available models:")
    for name, cfg in models.items():
        print(f"- {name} ({cfg['type']})")
    print("\n")

    # Test default model (local)
    default_model = get_default_model()
    print(f"Testing default model ({default_model['description']})...")
    try:
        answer = generate_response(
            context="Python is used for developing applications, web-based interfaces, and desktop applications.",
            query="Can you provide me with a list of Python libraries or tools that are commonly used in web development?",
            history="",
            model_name=None
        )
        print("Answer:\n", answer, "\n")
    except Exception as e:
        print("Error testing default model:", e, "\n")

    # Test all cloud models individually
    for name, cfg in models.items():
        if cfg["type"] == "cloud":
            print(f"Testing cloud model {name} ({cfg['description']})...")
            try:
                answer = generate_response(
                    context="Python is used for developing applications, web-based interfaces, and desktop applications.",
                    query="List some popular Python web development frameworks.",
                    history="",
                    model_name=name
                )
                print("Answer:\n", answer, "\n")
            except Exception as e:
                # Skip gracefully with reason
                print(f"⚠️ Skipping cloud model {name} due to error:\n{e}\n")

if __name__ == "__main__":
    test_models()