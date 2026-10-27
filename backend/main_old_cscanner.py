from fastapi import FastAPI, UploadFile, File, Form
from dotenv import load_dotenv
import os
import requests
from fastapi.middleware.cors import CORSMiddleware

# 加载.env环境变量
load_dotenv()
app = FastAPI()

# CORS跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 支持的语言
LANGUAGES = {
    "c": "C",
    "python": "Python",
    "java": "Java",
}

# 全局变量保存上传的代码 和 当前语言
code_content = ""
current_language = "c"

@app.post("/upload")
async def upload(file: UploadFile = File(...), language: str = Form("c")):
    global code_content, current_language
    try:
        raw_data = await file.read()
        # errors="replace" 遇到非法字节替换，不会抛出解码异常
        code_content = raw_data.decode("utf-8", errors="replace")
        # 校验语言参数，非法则回退到C
        current_language = language if language in LANGUAGES else "c"
        lang_name = LANGUAGES[current_language]
        return {"msg": f"{lang_name}文件上传成功，可以开始AI检测"}
    except Exception as e:
        print(f"upload 错误：{e}")
        return {"msg": f"上传失败：{str(e)}"}

@app.post("/audit")
async def audit():
    global code_content, current_language
    try:
        if not code_content.strip():
            return {"msg": "还没有上传代码，请先上传文件"}
        api_key = os.getenv("DASHSCOPE_API_KEY")
        print(f"读取到api_key: {api_key}")
        if not api_key:
            return {"msg": "错误：.env文件没有配置DASHSCOPE_API_KEY"}

        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        lang_name = LANGUAGES.get(current_language, "C")

        prompt = f"""
你是专业{lang_name}代码审计专家，请分析下面{lang_name}代码：
1. 找出编译错误（或语法错误）、运行时错误、内存漏洞、安全隐患
2. 标注错误行号，说明错误原理
3. 输出修复后的完整可运行代码

要求：
- 用以下表格格式输出问题汇总，每行一个：
| 类型 | 行号 | 问题描述 | 危害等级 | 原理说明 |
- 再输出修复方案说明
- 最后用```{lang_name}代码块输出修复后的完整可运行代码
{lang_name}代码：
{code_content}
        """

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "qwen-plus",
            "messages": [{"role": "user", "content": prompt}]
        }
        resp = requests.post(url, headers=headers, json=payload)
        res = resp.json()
        print("API原始返回：", res)
        # 增加判断：如果返回有error，直接返回错误信息
        if "error" in res:
            return {"msg": f"API调用失败：{res['error']['message']}"}
        if "choices" not in res:
            return {"msg": f"API返回异常，无choices字段：{res}"}
        return {"msg": res["choices"][0]["message"]["content"]}
    except Exception as e:
        print(f"audit接口异常：{e}")
        return {"msg": f"AI分析失败：{str(e)}"}
