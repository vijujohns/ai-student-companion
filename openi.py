import openai
from collections import defaultdict

# 🔑 Set your API key
openai.api_key = "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"

# Step 1: List all available models
try:
    models = openai.models.list()
except Exception as e:
    print("Error fetching models:", e)
    exit(1)

def categorize_model(model_id):
    model_id_lower = model_id.lower()
    if "gpt-4" in model_id_lower:
        return "GPT-4"
    elif "gpt-3.5" in model_id_lower:
        return "GPT-3.5"
    elif "embedding" in model_id_lower:
        return "Embedding"
    else:
        return "Other"

print("Testing models for usability and quota...\n")

results = []

for model in models.data:
    model_id = model.id
    category = categorize_model(model_id)

    print(f"Checking {category} model: {model_id}... ", end="", flush=True)

    try:
        if category in ["GPT-4", "GPT-3.5", "Other"]:
            openai.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=1
            )
            status = "✅ Usable"

        elif category == "Embedding":
            openai.embeddings.create(
                model=model_id,
                input="Test"
            )
            status = "✅ Usable"

    except openai.RateLimitError:
        status = "⚠️ Exceeded quota / rate limit"
    except openai.PermissionDeniedError:
        status = "❌ Not accessible / permission denied"
    except openai.BadRequestError as e:
        status = f"❌ Bad request: {str(e).splitlines()[0]}"
    except openai.OpenAIError as e:
        status = f"❌ Other error: {str(e).splitlines()[0]}"

    print(status)
    results.append((model_id, category, status))

# Print grouped results
categories = ["GPT-4", "GPT-3.5", "Embedding", "Other"]

for cat in categories:
    print(f"\n--- {cat} MODELS ---")
    for model_id, model_cat, status in results:
        if model_cat == cat:
            print(f"{model_id}: {status}")

# Summary table
summary = defaultdict(lambda: defaultdict(int))
for _, cat, status in results:
    summary[cat][status] += 1

print("\n--- SUMMARY TABLE ---")
print(f"{'Category':<12} | {'Usable':<7} | {'Quota/Limit':<15} | {'No Access/Error':<20}")
print("-"*60)
for cat in categories:
    usable = summary[cat].get("✅ Usable", 0)
    quota = summary[cat].get("⚠️ Exceeded quota / rate limit", 0)
    error = summary[cat].get("❌ Not accessible / permission denied", 0) + \
            sum(count for key, count in summary[cat].items() if key.startswith("❌ Bad request") or key.startswith("❌ Other error"))
    print(f"{cat:<12} | {usable:<7} | {quota:<15} | {error:<20}")

print("\nTesting complete.")