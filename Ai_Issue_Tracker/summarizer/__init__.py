"""Summarizer — OpenAI Codex CLI 또는 API 기반 뉴스 요약.

두 가지 모드 지원:
  1. Codex CLI 모드: `codex` CLI 명령을 subprocess로 호출 (로컬 개발)
  2. API 모드: OpenAI API 직접 호출 (Docker 배포, fallback)

Codex CLI 설치:
  npm install -g @openai/codex
  # 또는 VS Code Codex 확장에서 사용
"""

import json
import logging
import os
import subprocess
import shutil
import tempfile
from pathlib import Path

from config import load_sources, openai_api_key, codex_model, summary_language

logger = logging.getLogger(__name__)


def summarize_items(items: list[dict]) -> str:
    """뉴스 아이템 리스트를 요약하여 텔레그램 메시지 형식으로 반환.

    Codex CLI가 설치되어 있으면 CLI 사용, 없으면 API fallback.
    """
    if not items:
        return "📭 새로운 뉴스가 없습니다."

    # Codex CLI 존재 여부 확인
    if shutil.which("codex"):
        logger.info("[Summarizer] Using Codex CLI mode")
        return _summarize_with_codex_cli(items)
    else:
        logger.info("[Summarizer] Codex CLI not found, using OpenAI API fallback")
        return _summarize_with_api(items)


def _build_prompt(items: list[dict]) -> str:
    """요약용 프롬프트 생성."""
    sources_cfg = load_sources()
    system_prompt = sources_cfg.get("summarizer", {}).get("system_prompt", "")
    lang = summary_language()
    category_emoji = sources_cfg.get("category_emoji", {})

    # 아이템을 소스별로 그룹핑
    grouped: dict[str, list[dict]] = {}
    for item in items:
        src = item.get("source_type", "unknown")
        grouped.setdefault(src, []).append(item)

    items_text = ""
    for source_type, group in grouped.items():
        items_text += f"\n## Source: {source_type}\n"
        for i, item in enumerate(group, 1):
            emoji = category_emoji.get(item.get("category", ""), "📌")
            items_text += f"""
{emoji} Item {i}:
- Title: {item.get('title', 'N/A')}
- Source: {item.get('source', 'N/A')}
- URL: {item.get('url', 'N/A')}
- Content: {(item.get('content', '') or '')[:300]}
"""

    prompt = f"""{system_prompt}

다음 {len(items)}개의 AI/Tech 뉴스 아이템을 분석하고 요약해주세요.

{items_text}

출력 형식 (텔레그램 마크다운):
1. 전체 트렌드 한줄 요약
2. 카테고리별 그룹핑된 뉴스 요약 (중요도 높은 순)
3. 각 항목은 이모지 + 한줄 요약 + 링크

언어: {"한국어" if lang == "ko" else lang}
형식: 텔레그램 MarkdownV2 호환
"""
    return prompt


def _summarize_with_codex_cli(items: list[dict]) -> str:
    """Codex CLI를 subprocess로 호출하여 요약."""
    prompt = _build_prompt(items)

    # 프롬프트를 임시 파일에 저장 (긴 프롬프트 처리)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(prompt)
        prompt_file = f.name

    try:
        # codex CLI 호출
        # --quiet: 인터랙티브 UI 비활성화
        # --full-auto: 자동 승인 모드
        result = subprocess.run(
            [
                "codex",
                "--quiet",
                "--full-auto",
                "--model", codex_model(),
                f"Read the file {prompt_file} and follow the instructions in it. "
                f"Output ONLY the formatted summary text, nothing else.",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "OPENAI_API_KEY": openai_api_key()},
        )

        if result.returncode == 0 and result.stdout.strip():
            summary = result.stdout.strip()
            logger.info(f"[Summarizer] Codex CLI success: {len(summary)} chars")
            return summary
        else:
            logger.warning(f"[Summarizer] Codex CLI failed: {result.stderr}")
            return _summarize_with_api(items)

    except subprocess.TimeoutExpired:
        logger.error("[Summarizer] Codex CLI timeout (120s)")
        return _summarize_with_api(items)
    except Exception as e:
        logger.error(f"[Summarizer] Codex CLI error: {e}")
        return _summarize_with_api(items)
    finally:
        Path(prompt_file).unlink(missing_ok=True)


def _summarize_with_api(items: list[dict]) -> str:
    """OpenAI API 직접 호출 (fallback)."""
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("[Summarizer] openai package not installed")
        return _format_fallback(items)

    api_key = openai_api_key()
    if not api_key:
        logger.error("[Summarizer] OPENAI_API_KEY not set")
        return _format_fallback(items)

    client = OpenAI(api_key=api_key)
    prompt = _build_prompt(items)
    model = codex_model()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an AI news digest curator."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=2048,
            temperature=0.3,
        )
        summary = response.choices[0].message.content.strip()
        logger.info(f"[Summarizer] API success: {len(summary)} chars (model={model})")
        return summary

    except Exception as e:
        logger.error(f"[Summarizer] API error: {e}")
        return _format_fallback(items)


def _format_fallback(items: list[dict]) -> str:
    """AI 요약 실패 시 단순 리스트 형식 fallback."""
    sources_cfg = load_sources()
    category_emoji = sources_cfg.get("category_emoji", {})

    lines = [f"📋 *AI 뉴스 다이제스트* ({len(items)}건)\n"]

    for item in items[:20]:
        emoji = category_emoji.get(item.get("category", ""), "📌")
        title = item.get("title", "N/A")
        url = item.get("url", "")
        source = item.get("source", "")
        lines.append(f"{emoji} {title}")
        if url:
            lines.append(f"   🔗 {url}")
        if source:
            lines.append(f"   📎 {source}")
        lines.append("")

    return "\n".join(lines)
