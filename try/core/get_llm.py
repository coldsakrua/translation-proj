
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

# Moonshot AI (Kimi) API 配置
# 你需要前往 https://platform.moonshot.cn/ 申请 API Key
llm = ChatOpenAI(
    base_url="https://api.moonshot.cn/v1",
    api_key="sk-PcRFk2s6jqw8Eav6dIou5Z9oyXz3X0pDI6vBMeDq6WjFrMj7",  # 替换为你从 Kimi 开放平台申请的 API Key
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
