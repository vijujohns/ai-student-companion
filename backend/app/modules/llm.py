from llama_cpp import Llama

#MODEL_PATH = "app/models/phi-2.Q4_K_M.gguf"
MODEL_PATH = "app/models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
llm = None


def load_model():
    global llm

    if llm is None:
        llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=1024,
            n_threads=6,
            n_batch=128
        )

    return llm

def generate_answer(prompt):
    model = load_model()

    # Hard truncate (safety fallback)
    prompt = prompt[:3000]

    response = model(
        prompt,
        max_tokens=120,
        temperature=0.2,
        top_p=0.9,
        stop=["QUESTION:", "RESPONSE:", "Question:", "Answer:", "Possible rewrite"]
    )

    return response["choices"][0]["text"].strip()