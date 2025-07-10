import requests

API_URL = "http://110.42.252.68:8080/api/generate"

payload = {
    "model": "qwen2.5vl:32b",  # 确保与 /api/tags 返回一致
    "prompt": "你好，能介绍一下你自己吗？",
    "stream": False
}

response = requests.post(API_URL, json=payload)

if response.status_code == 200:
    data = response.json()
    print("🤖 回复：", data["response"])
else:
    print("❌ 请求失败，状态码：", response.status_code)