import os
from pathlib import Path

from langchain_openai import ChatOpenAI
# 初始化模型 (推荐使用支持 Function Calling 强的模型)
# OpenRouter每天有限额
# llm = ChatOpenAI(
#     base_url="https://openrouter.ai/api/v1",
#     api_key="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",
#     model="nex-agi/deepseek-v3.1-nex-n1:free",
#     default_headers={
#         "HTTP-Referer": "https://your-site.com",
#         "X-Title": "My LangGraph Agent",
#     }
# )

# llm = ChatOpenAI(
#     base_url="https://api.chatanywhere.tech",
#     # api_key="sk-HyWVzAcGxCHILLglC4jiGYbnzP6pu4MiW78nUuILby0y5NzH",
#     api_key="sk-C5P2uZhJDLypJMjqtjnvbmqfYFUUENFgBRYlIbw3YROkvFUM", #ly
#     model="gpt-4o-mini",
#     default_headers={
#         "HTTP-Referer": "https://your-site.com",
#         "X-Title": "My LangGraph Agent",
#     }
# )

from langchain_google_genai import ChatGoogleGenerativeAI


def load_api_key():
    """
    从 api.txt 文件加载 API key
    
    Returns:
        str: API key，如果文件不存在则返回空字符串
    """
    # 获取当前文件所在目录
    current_dir = Path(__file__).parent
    api_file = current_dir / "api.txt"
    
    if api_file.exists():
        try:
            with open(api_file, 'r', encoding='utf-8') as f:
                api_key = f.read().strip()
                if api_key:
                    return api_key
        except Exception as e:
            print(f"⚠️  读取 API key 文件失败: {e}")
    
    # 如果文件不存在或读取失败，尝试从环境变量读取
    api_key = os.getenv("MOONSHOT_API_KEY", "")
    if api_key:
        return api_key
    
    print("⚠️  警告: 未找到 API key")
    print(f"   请创建文件: {api_file}")
    print("   或在环境变量中设置 MOONSHOT_API_KEY")
    return ""


# Moonshot AI (Kimi) API 配置
# 你需要前往 https://platform.moonshot.cn/ 申请 API Key
# API key 从 try/core/api.txt 文件读取（该文件不会被提交到仓库）
api_key = load_api_key()

if not api_key:
    raise ValueError(
        f"API key 未配置！\n"
        f"请创建文件 try/core/api.txt 并写入你的 API key，\n"
        f"或在环境变量中设置 MOONSHOT_API_KEY"
    )

llm = ChatOpenAI(
    base_url="https://api.moonshot.cn/v1",
    api_key=api_key,
    model="moonshot-v1-8k",  # 或 "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"
    temperature=0.6,
    default_headers={
        "HTTP-Referer": "https://your-site.com",
        "X-Title": "My LangGraph Agent",
    }
)

# 初始化 Gemini 模型
# 你需要前往 https://makersuite.google.com/app/apikey 获取免费的 API 密钥
# llm = ChatGoogleGenerativeAI(
#     model="gemini-2.5-flash",  # 或 "gemini-1.5-flash-latest"（更快、更经济）
#     api_key="AIzaSyDuGdGGlPVnttpxcE-nJyjpjxeAYWlV7tQ",  # 替换为你的实际密钥
# )
