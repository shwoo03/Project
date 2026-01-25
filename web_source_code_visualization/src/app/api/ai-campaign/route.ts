import { NextResponse } from 'next/server';
import Groq from 'groq-sdk';

const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

export async function POST(req: Request) {
    try {
        const { stage, data } = await req.json(); // stage: 'verify' | 'plan' | 'report'

        let systemPrompt = "You are a CTF Auto-Solver Agent. You must respond in JSON format."; // Added 'You must respond in JSON format.'
        let userPrompt = "";

        if (stage === 'verify') {
            systemPrompt += " 당신의 역할은 보안 취약점을 분석하는 전문가입니다. 매우 공격적으로 분석하세요. 논리적 결함(Logic Flaws), 인증 우회(Authentication Bypass), 하드코딩된 로직, 인젝션 등을 찾으세요. 결과는 반드시 JSON으로 반환: { isVulnerable: boolean, reason: string }.";
            userPrompt = `다음 코드를 '${data.vulnType}' 관점에서 분석하되, 인증 우회나 논리적 결함도 함께 확인해주세요:\n\n\`\`\`\n${data.snippet}\n\`\`\`\n\n취약한가요? 확실하지 않으면 true라고 하세요. 한국어로 답변할 필요는 없으며 JSON만 반환하세요.`;
        }
        else if (stage === 'plan') {
            systemPrompt += " 당신의 역할은 구체적인 익스플로잇 페이로드를 생성하는 것입니다. 결과는 반드시 JSON으로 반환: { payloads: [{ name: string, param: string, value: string }] }.";
            userPrompt = `대상: ${data.method} ${data.path}\n취약점: ${data.vulnType}\n코드:\n\`\`\`${data.snippet}\n\`\`\`\n\n위 코드를 분석하여 **정확한 변수명(쿠키명, 파라미터명)**을 사용하는 공격 페이로드 3개를 생성하세요.\n[중요 규칙]\n1. 코드를 보고 정확한 쿠키 이름(예: 'username', 'session_id')을 사용해야 합니다. 절대 추측하지 마세요.\n2. 인증 로직을 우회할 수 있는 '구체적인 값'(예: admin, true)을 넣으세요.\n3. 불필요한 헤더 공격은 제외하고, 코드가 실제로 검사하는 값에 집중하세요.`;
        }
        else if (stage === 'report') {
            systemPrompt += " 당신은 개발자를 위한 시니어 보안 가이드입니다. '취약점 분석 결과(Findings)'를 바탕으로 **구체적이고 이해하기 쉬운** 보고서를 작성하세요.\n\n[중요 원칙]\n1. 교과서적인 보안 용어(예: 세션 고정, CSRF)를 나열하지 마세요. **실제 코드의 논리적 결함**을 설명하세요.\n2. \"왜\" 취약한지 직관적으로 설명하세요. (예: \"쿠키 값이 암호화되지 않아서 사용자가 수정할 수 있습니다.\")\n3. Findings에 있는 페이로드가 어떻게 방어 로직을 뚫었는지 단계별로 설명하세요.\n4. **절대 환각(Hallucination) 금지**: Findings에 없는 공격 기법(예: Basic Auth, Token Replay)을 언급하지 마세요. 오직 발견된 취약점만 다루세요.\n5. **해결 방법(Remediation) 섹션은 제외하세요.** 문제점 분석에만 집중하세요.\n\n결과는 JSON으로 반환: { markdown: string }.";

            // findings is now passed in data
            const findingsInfo = data.findings ? JSON.stringify(data.findings, null, 2) : "No detailed findings.";
            userPrompt = `공격 로그:\n${JSON.stringify(data.logs)}\n\n상세 분석 결과 (Findings):\n${findingsInfo}\n\n위 정보를 바탕으로 다음 구조의 보고서를 작성하세요:\n# [Target Name] 보안 점검 결과\n## 1. 핵심 요약 (Summary)\n## 2. 취약점 원인 (Root Cause)\n- **문제가 되는 코드**: (Findings 인용)\n- **상세 분석**: (이 코드가 왜 위험한지 초보자도 이해하게 설명)\n## 3. 공격 시연 (Exploit)\n- **사용된 값**: (Findings payload 중 1~2개)\n- **공격 원리**: (이 값을 넣었을 때 서버가 어떻게 오작동했는지)`;
        }

        // Model Selection Strategy based on Rate Limits
        // 'verify': Complex logic needed now -> 'llama-3.3-70b-versatile'
        // 'plan'/'report': High reasoning needed -> 'llama-3.3-70b-versatile'
        let model = 'llama-3.3-70b-versatile';

        const completion = await groq.chat.completions.create({
            messages: [
                { role: 'system', content: systemPrompt },
                { role: 'user', content: userPrompt }
            ],
            model: model,
            temperature: 0.1,
            response_format: { type: 'json_object' }
        });

        const result = completion.choices[0]?.message?.content || "{}";
        return NextResponse.json(JSON.parse(result));

    } catch (error: any) {
        return NextResponse.json({ error: error.message }, { status: 500 });
    }
}
