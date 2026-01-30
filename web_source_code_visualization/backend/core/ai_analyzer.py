
import os
import groq
import traceback
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
            print(f"[AI] GROQ_API_KEY loaded successfully from {root_env}")
            self.client = groq.Groq(api_key=self.api_key)

        # Priority List - 안정적인 모델 우선
        self.models = [
            "llama-3.3-70b-versatile",    # 1. 가장 안정적
            "llama-3.1-8b-instant",       # 2. 빠른 fallback
            "qwen/qwen3-32b",             # 3. 대안
        ]

    def analyze_code(self, code: str, context: str = "", referenced_files: Dict[str, str] = None) -> Dict[str, Any]:
        if not self.client:
            return {
                "error": "GROQ_API_KEY is missing. Please set it in .env file.",
                "analysis": "AI Analysis is disabled."
            }
            
        system_prompt = (
            "당신은 CTF/Wargame 문제 풀이 및 웹 해킹 전문가입니다. "
            "주어진 코드와 프로젝트 전체 맥락(Context)을 분석하여 보안 취약점을 찾아내세요. "
            "이 코드는 워게임(Wargame) 문제의 일부이므로, **공격 시나리오와 Flag 획득 방법**에만 집중해야 합니다.\n\n"
            "**응답 가이드라인 (반드시 준수):**\n"
            "1. **Markdown 포맷 적용**: Notion 스타일의 깔끔한 Markdown을 사용한다.\n"
            "2. **구조화된 헤더**: 대주제는 `#`, 중주제는 `##`, 소주제는 `###`을 사용하여 계층 구조를 명확히 한다.\n"
            "3. **문체 통일**: 모든 문장은 반드시 '**~다.**', '**~이다.**', '**~하다.**', '**~있다.**' 등의 평서문으로 끝맺는다.\n"
            "4. **내용 구성**:\n"
            "   - `# 상태`: '✅ **안전함**' 또는 '🚨 **취약함**' 표시.\n"
            "   - `# 핵심 취약점`: 발견된 취약점 명칭 (예: Reflected XSS, Cookie Injection).\n"
            "   - `# 공격 분석`: 취약점 발생 원인과 악용 로직을 논리적으로 서술한다.\n"
            "   - `# PoC (Proof of Concept)`: 공격 페이로드, 명령어, 공격 순서 등을 코드 블록과 함께 상세히 작성한다.\n\n"
            "**주의사항:**\n"
            "- '대응 방안'이나 '보안 가이드'는 **절대 포함하지 않는다**.\n"
            "- 불필요한 서론이나 인사말은 생략한다.\n"
            "- 반드시 **한국어(Korean)**로 작성한다."
        )
        
        # Build Reference Context
        ref_context = ""
        if referenced_files:
            ref_context = "\n\n**[참고 파일 및 함수 정의]**:\n"
            for fpath, fcontent in referenced_files.items():
                ref_context += f"--- {fpath} ---\n{fcontent}\n\n"

        user_prompt = f"Code to analyze:\n```\n{code}\n```\n\nContext:\n{context}\n{ref_context}"
        
        # 프롬프트 길이 체크 (토큰 제한 방지)
        total_chars = len(system_prompt) + len(user_prompt)
        print(f"[AI] Total prompt length: {total_chars} chars (~{total_chars // 4} tokens)")
        
        if total_chars > 30000:  # 약 7500 토큰 이상이면 경고
            print(f"[AI] Warning: Prompt is very long, may hit token limits")

        errors_log = []
        for model in self.models:
            try:
                print(f"[AI] Attempting analysis with model: {model}")
                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    model=model,
                    temperature=0.1,
                    max_tokens=2048,
                    timeout=60,  # 60초 타임아웃
                )
                
                analysis = chat_completion.choices[0].message.content
                print(f"[AI] Success with model: {model}")
                return {
                    "model": model,
                    "analysis": analysis,
                    "success": True
                }

            except groq.RateLimitError as e:
                error_msg = f"Rate limit for {model}: {str(e)[:100]}"
                print(f"[AI] {error_msg}")
                errors_log.append(error_msg)
                continue
            except groq.NotFoundError as e:
                error_msg = f"Model {model} not found: {str(e)[:100]}"
                print(f"[AI] {error_msg}")
                errors_log.append(error_msg)
                continue
            except groq.APIConnectionError as e:
                error_msg = f"Connection error for {model}: {str(e)[:100]}"
                print(f"[AI] {error_msg}")
                errors_log.append(error_msg)
                continue
            except groq.APITimeoutError as e:
                error_msg = f"Timeout for {model}: {str(e)[:100]}"
                print(f"[AI] {error_msg}")
                errors_log.append(error_msg)
                continue
            except Exception as e:
                error_msg = f"Error with {model}: {type(e).__name__}: {str(e)[:150]}"
                print(f"[AI] {error_msg}")
                print(f"[AI] Traceback: {traceback.format_exc()}")
                errors_log.append(error_msg)
                continue

        return {
            "error": "All AI models failed or rate limited.",
            "analysis": f"분석 실패. 상세 오류:\n" + "\n".join(errors_log) if errors_log else "알 수 없는 오류",
            "success": False
        }
