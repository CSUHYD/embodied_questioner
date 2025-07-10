import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from FlagEmbedding import FlagAutoModel
import numpy as np

class EmbeddingServer:
    def __init__(self, model_path="BAAI/bge-small-en-v1.5"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = FlagAutoModel.from_finetuned(
                                    model_path,
                                    query_instruction_for_retrieval="Represent this sentence for searching relevant passages:",
                                    use_fp16=True,
                                    devices=["cpu"])
        # self.model = AutoModelForSequenceClassification.from_pretrained(
        #     model_path).eval()

    def get_most_similar_pair(self, s1, s2):
        # pairs = [['what is panda?', 'hi'], ['what is panda?', 'The giant panda (Ailuropoda melanoleuca), sometimes called a panda bear or simply panda, is a bear species endemic to China.']]
        
        with torch.no_grad():
            # inputs = self.tokenizer(pairs, padding=True, truncation=True, return_tensors='pt', max_length=512).to(self.model.device)
            # scores = self.model(**inputs, return_dict=True).logits.view(-1, ).float()
            embeddings_1 = self.model.encode(s1)
            embeddings_2 = self.model.encode(s2)

        similarity = embeddings_1 @ embeddings_2.T
        index = np.argmax(similarity[0])
        if list(similarity[0])[index] > 0.2:
            return s2[index], list(similarity[0])
        else:
            print(s2[index], list(similarity[0])[index])
            return "No Suitable Object", list(similarity[0])

if __name__=="__main__":
    server = EmbeddingServer()
    import requests
    from collections import OrderedDict
    s1 = ["fridge"]
    s2 = ["CounterTop","Book","HousePlant","Cabinet","Window","Stool","ShelvingUnit","Fridge"]
    a  = server.get_most_similar_pair(s1, s2)
    print(a)