import os
import groq
from typing import Dict, Any
from dotenv import load_dotenv

class AIAnalyzer:
    def __init__(self):
        # Force load .env from project root (3 levels up from backend/core/ai_analyzer.py)
        # backend/core/ai_analyzer.py -> backend/core -> backend -> root
        root_env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
        load_dotenv(root_env)
        
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            print(f"Warning: GROQ_API_KEY is not set. Tried loading from: {root_env}")
            self.client = None
        else:
            self.client = groq.Groq(api_key=self.api_key)

        # Priority List (User Defined)
        self.models = [
            "openai/gpt-oss-120b",        # 1. 1st Priority
            "llama-3.3-70b-versatile",    # 2. 2nd Priority
            "qwen/qwen3-32b",             # 3. 3rd Priority
            "llama-3.1-8b-instant"        # 4. Ultimate Fallback (added for safety)
        ]

    def analyze_code(self, code: str, context: str = "") -> Dict[str, Any]:
        if not self.client:
            return {
                "error": "GROQ_API_KEY is missing. Please set it in .env file.",
                "analysis": "AI Analysis is disabled."
            }

        system_prompt = (
            "당신은 CTF/Wargame 문제 풀이 및 웹 해킹 전문가입니다. "
            "주어진 코드와 프로젝트 전체 맥락(Context)을 분석하여 보안 취약점을 찾아내세요. "
            "이 코드는 워게임(Wargame) 문제의 일부이므로, 공격 시나리오와 Flag 획득 가능성에 집중해야 합니다.\n\n"
            "응답 형식 (반드시 Markdown 사용):\n"
            "1. **상태**: '✅ **안전함**' 또는 '🚨 **취약함**' 으로 시작.\n"
            "2. **요약**: 취약점에 대한 1~2문장 요약.\n"
            "3. **상세 분석**: 발견된 취약점, 원인, 공격 방법 등을 상세히 설명.\n"
            "4. **공격 시나리오 (PoC)**: 가능하다면 공격을 위한 페이로드 예시 포함.\n"
            "5. **대응 방안**: 코드를 어떻게 수정해야 하는지 제안.\n\n"
            "반드시 **한국어(Korean)**로 답변하세요. "
            "단순한 코드 설명보다는, 해커의 관점에서 어떻게 악용할 수 있는지 설명하세요."
        )

        user_prompt = f"Code to analyze:\n```\n{code}\n```"

        for model in self.models:
            try:
                print(f"Attempting analysis with model: {model}")
                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    model=model,
                    temperature=0.1,
                    max_tokens=2048,
                )
                
                analysis = chat_completion.choices[0].message.content
                return {
                    "model": model,
                    "analysis": analysis,
                    "success": True
                }

            except groq.RateLimitError as e:
                print(f"Rate limit exceeded for {model}. Falling back...")
                continue
            except groq.NotFoundError as e:
                print(f"Model {model} not found or deprecated. Falling back...")
                continue
            except Exception as e:
                print(f"Error with model {model}: {e}")
                # For other errors, we might want to try next model or fail?
                # Let's try next model just in case it's a specific model outage
                continue

        return {
            "error": "All AI models failed or rate limited.",
            "analysis": "Could not complete analysis due to high traffic.",
            "success": False
        }
