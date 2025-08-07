import requests
import json
import time
import os
from datetime import datetime


def get_data_engine_path():
    """获取data_engine目录的绝对路径"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return script_dir


def get_project_root():
    """获取项目根目录的绝对路径"""
    data_engine_path = get_data_engine_path()
    return os.path.dirname(data_engine_path)


def load_prompt_config(config_path="config/prompt_config.json"):
    """加载 prompt 配置文件"""
    if not os.path.isabs(config_path):
        config_path = os.path.join(get_data_engine_path(), config_path)
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Config file {config_path} not found, using default config")
        return {}

# 默认配置
PROMPT_CONFIG = load_prompt_config()

    
class LLMRequestError(Exception):
    pass  

class LLMAPI:
    def __init__(self, model):  # qwen3:32b, llama3:8b, etc.
        self.model = model
        self.api_url = "http://110.42.252.68:8080/api/generate"
        

    

    def llm_request(self,
                    systext,
                    usertext,
                    max_tokens=1500,
                    retry_limit=3,
                    response_format=None,
                    json_schema=None):
        """
        发送LLM请求到Ollama API
        
        Args:
            systext: 系统提示文本
            usertext: 用户提示文本
            max_tokens: 最大token数
            retry_limit: 重试次数
            response_format: 响应格式，"json"表示要求JSON格式输出
            json_schema: JSON schema定义（可选）
        """
        
        # 如果指定了JSON格式，修改提示文本
        if response_format == "json":
            if "json" not in systext.lower():
                systext += "\n\nAlways respond with valid JSON format only. Do not include any text outside the JSON structure."
            
            if json_schema:
                schema_instruction = f"\n\nThe JSON response must follow this schema:\n{json.dumps(json_schema, indent=2)}"
                usertext += schema_instruction
        
        # 构建完整的提示文本
        full_prompt = f"{systext}\n\n{usertext}"
        
        
        # 构建Ollama API请求payload
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.7 if response_format == "json" else 0.9  # JSON时降低温度
            }
        }
        
        # 如果需要JSON格式输出，添加format参数
        if response_format == "json":
            payload["format"] = "json"
        
        
        retry_count = 0
        while retry_count < retry_limit: 
            try:
                t1 = time.time()
                print(f"********* start call {self.model} *********")
                
                # 发送请求到Ollama API
                response = requests.post(self.api_url, json=payload, timeout=60)
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("response", "")
                    
                    # 如果要求JSON格式，验证输出
                    if response_format == "json":
                        try:
                            # 尝试解析JSON以验证格式
                            json.loads(content)
                            print("✓ Valid JSON response received")
                        except json.JSONDecodeError as e:
                            print(f"⚠ JSON parsing failed: {e}")
                            print(f"Raw response: {content}")
                    

                    t2 = time.time() - t1
                    print(f"********* end call {self.model}: {t2:.2f} *********")
                    
                    return content
                else:
                    print(f"API request failed with status code: {response.status_code}")
                    print(f"Response: {response.text}")
                    
            except Exception as ex:
                print(f"Attempt call {self.model} {retry_count + 1} failed: {ex}")
                time.sleep(300)
                retry_count += 1
        
        return "Failed to generate completion after multiple attempts."

    def llm_request_json(self, systext, usertext, json_schema=None, **kwargs):
        """便捷方法：专门用于获取JSON格式响应"""
        return self.llm_request(
            systext, 
            usertext, 
            response_format="json", 
            json_schema=json_schema,
            **kwargs
        )

    def parse_json_response(self, response):
        """安全解析JSON响应"""
        try:
            return json.loads(response), None
        except json.JSONDecodeError as e:
            return None, str(e)


def save_data_to_json(json_data, base_path):
    """保存JSON数据到文件"""
    os.makedirs(os.path.dirname(base_path), exist_ok=True)

    try:
        with open(base_path, "r") as f:
            existing_data = json.load(f)
            if not isinstance(existing_data, list):
                existing_data = []
    except (FileNotFoundError, json.JSONDecodeError):
        existing_data = []

    # append
    existing_data.append(json_data)

    # write
    with open(base_path, "w") as f:
        json.dump(existing_data, f, indent=4)
    
    print("save json data to path:", base_path)


# JSON Schema 样例
JSON_SCHEMAS = {
    "basic_info": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "姓名"},
            "age": {"type": "number", "description": "年龄"},
            "city": {"type": "string", "description": "所在城市"}
        },
        "required": ["name"]
    },
    
    "task_analysis": {
        "type": "object",
        "properties": {
            "task_type": {"type": "string", "enum": ["classification", "generation", "analysis", "other"]},
            "complexity": {"type": "string", "enum": ["simple", "medium", "complex"]},
            "estimated_time": {"type": "number", "description": "预估完成时间(分钟)"},
            "required_resources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "所需资源列表"
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1}
        },
        "required": ["task_type", "complexity"]
    },
    
    "code_review": {
        "type": "object",
        "properties": {
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "line": {"type": "number"},
                        "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                        "description": {"type": "string"},
                        "suggestion": {"type": "string"}
                    },
                    "required": ["severity", "description"]
                }
            },
            "overall_score": {"type": "number", "minimum": 0, "maximum": 10},
            "summary": {"type": "string"}
        },
        "required": ["issues", "overall_score", "summary"]
    },
    
    "text_classification": {
        "type": "object",
        "properties": {
            "category": {"type": "string"},
            "subcategory": {"type": "string"},
            "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
            "reasoning": {"type": "string"},
            "tags": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["category", "confidence_score"]
    },
    
    "qa_response": {
        "type": "object",
        "properties": {
            "answer": {"type": "string", "description": "问题答案"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "信息来源"
            },
            "follow_up_questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "相关问题建议"
            }
        },
        "required": ["answer"]
    }
}


if __name__ == "__main__":
    # 测试代码
    model = "qwen3:32b"
    llmapi = LLMAPI(model)
    
    print("=" * 60)
    print("纯LLM JSON格式测试")
    print("=" * 60)
    
    # 测试1: 基本信息提取
    print("\n测试1: 基本信息提取")
    print("-" * 40)
    systext = "你是一个信息提取助手，需要从文本中提取结构化信息。"
    usertext = "我叫张三，今年25岁，住在北京市。请提取我的基本信息。"
    
    response = llmapi.llm_request_json(
        systext, 
        usertext, 
        json_schema=JSON_SCHEMAS["basic_info"]
    )
    print("Response:", response)
    
    json_data, error = llmapi.parse_json_response(response)
    if json_data:
        print("✓ Parsed JSON:", json.dumps(json_data, indent=2, ensure_ascii=False))
    else:
        print(f"✗ JSON parsing failed: {error}")
    
    # 测试2: 任务分析
    print("\n测试2: 任务分析")
    print("-" * 40)
    systext = "你是一个任务分析专家，需要分析给定任务的类型、复杂度和所需资源。"
    usertext = "请帮我分析这个任务：开发一个机器人路径规划算法，能够在复杂环境中避障并找到最优路径。"
    
    response = llmapi.llm_request_json(
        systext,
        usertext,
        json_schema=JSON_SCHEMAS["task_analysis"]
    )
    print("Response:", response)
    
    json_data, error = llmapi.parse_json_response(response)
    if json_data:
        print("✓ Parsed JSON:", json.dumps(json_data, indent=2, ensure_ascii=False))
    else:
        print(f"✗ JSON parsing failed: {error}")
    
    # 测试3: 文本分类
    print("\n测试3: 文本分类")
    print("-" * 40)
    systext = "你是一个文本分类专家，需要对给定文本进行分类并给出详细分析。"
    usertext = "最近股市表现不佳，投资者情绪低落，建议谨慎投资，关注风险管理。"
    
    response = llmapi.llm_request_json(
        systext,
        usertext,
        json_schema=JSON_SCHEMAS["text_classification"]
    )
    print("Response:", response)
    
    json_data, error = llmapi.parse_json_response(response)
    if json_data:
        print("✓ Parsed JSON:", json.dumps(json_data, indent=2, ensure_ascii=False))
    else:
        print(f"✗ JSON parsing failed: {error}")
    
    # 测试4: 问答系统
    print("\n测试4: 问答系统")
    print("-" * 40)
    systext = "你是一个智能问答助手，需要准确回答用户问题并提供相关信息。"
    usertext = "什么是机器学习？它有哪些主要应用领域？"
    
    response = llmapi.llm_request_json(
        systext,
        usertext,
        json_schema=JSON_SCHEMAS["qa_response"]
    )
    print("Response:", response)
    
    json_data, error = llmapi.parse_json_response(response)
    if json_data:
        print("✓ Parsed JSON:", json.dumps(json_data, indent=2, ensure_ascii=False))
    else:
        print(f"✗ JSON parsing failed: {error}")
    
    # 测试5: 代码审查（纯文本）
    print("\n测试5: 代码审查")
    print("-" * 40)
    systext = "你是一个代码审查专家，需要分析代码质量并给出改进建议。"
    usertext = '''请审查以下Python代码：
                def process_data(data):
                    result = []
                    for i in range(len(data)):
                        if data[i] > 0:
                            result.append(data[i] * 2)
                    return result'''
    
    response = llmapi.llm_request_json(
        systext,
        usertext,
        json_schema=JSON_SCHEMAS["code_review"]
    )
    print("Response:", response)
    
    json_data, error = llmapi.parse_json_response(response)
    if json_data:
        print("✓ Parsed JSON:", json.dumps(json_data, indent=2, ensure_ascii=False))
    else:
        print(f"✗ JSON parsing failed: {error}")
    
    print("\n" + "=" * 60)
    print("测试完成！可用的JSON Schema模板:")
    print("=" * 60)
    for schema_name in JSON_SCHEMAS.keys():
        print(f"- {schema_name}")
    print("\n可通过 JSON_SCHEMAS['{schema_name}'] 获取对应的schema定义")