class ModelManager:
    def __init__(self):
        self.available_models = ["LLaMA-7B", "Math-specialized", "Hindi-specialized"]

    def get_models(self):
        return self.available_models

    def select_model(self, model_name):
        if model_name in self.available_models:
            return model_name
        return None
