from sentence_transformers import SentenceTransformer
from transformers import BlipProcessor, BlipForConditionalGeneration
import torch

text_model = SentenceTransformer('all-MiniLM-L6-v2')
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
image_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")

def embed_text(text_list):
    return text_model.encode(text_list, convert_to_tensor=True)

def embed_image(image):
    pixel_values = processor(images=image, return_tensors="pt").pixel_values
    with torch.no_grad():
        features = image_model(pixel_values=pixel_values)
    return features.last_hidden_state.mean(dim=1)
