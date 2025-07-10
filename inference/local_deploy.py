from flask import Flask, request, jsonify
from predictor.hf_infer import HfServer
from predictor.vllm_infer import VllmServer
from predictor.embedding_server import EmbeddingServer
import os
import argparse
# os.environ["CUDA_VISIBLE_DEVICES"] = "5"
def http_server(args):
    app = Flask(__name__)
    if args.frame == "hf":
        model_server = HfServer(args.model_type, args.model_name)
    elif args.frame == "vllm":
        model_server = VllmServer(args.model_type, args.model_name)
    
    @app.route("/generate", methods=["POST"])
    def generate():
        data = request.json
        
        generation_parms = data['generation_parms'] if "generation_parms" in data else None
        outputs, outputs_length = model_server.generate(data['inputs'], generation_parms)
        if isinstance(outputs,list):
            outputs = outputs[0]
        return jsonify({"output_text":outputs, "output_len":outputs_length})

    @app.route("/chat", methods=["POST"])
    def chat():
        data = request.json
        generation_parms = data['generation_parms'] if "generation_parms" in data else None
        outputs, outputs_length = model_server.chat(data['inputs'], generation_parms)
        if isinstance(outputs,list):
            outputs = outputs[0]
        return jsonify({"output_text":outputs, "output_len":outputs_length})

    app.run(port=args.port)

def embedding_http_server(args):
    app = Flask(__name__)
    model_server = EmbeddingServer()
    
    @app.route("/match", methods=["POST"])
    def match():
        data = request.json
        s1 = data["s1"]
        s2 = data["s2"]
        target_obj, _ = model_server.get_most_similar_pair(s1, s2)
        
        return jsonify({"target_obj":target_obj})

    app.run(port=args.port)
    
if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--embedding", type=int, default=0, help="")
    parser.add_argument("--frame", type=str, default="hf", help="The frame to be used.")
    parser.add_argument("--model_type", type=str, default="qwen2_5_vl", help="The model type to be used.")
    parser.add_argument("--model_name", type=str, default="Qwen/Qwen2.5-VL-3B-Instruct", help="The model name to be used.")
    parser.add_argument("--port", type=int, default=10000, help="The port to be used.")
    args = parser.parse_args()

    if args.embedding==1:
        embedding_http_server(args)
    else:
        http_server(args)