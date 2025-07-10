from openai import OpenAI

client = OpenAI(
    api_key = "d1nmi0bm1orcf176oefg",   # 替换为你的API密钥
    base_url = "https://llmapi.tongji.edu.cn/v1"
)
chat_completion = client.chat.completions.create(
    model="Qwen3-235B",  # 替换为你的模型名称
    messages=[
        {
            "role": "user",
            "content": "地球的半径是多少?",
        }
    ]
)

print(chat_completion.choices[0].message.content)