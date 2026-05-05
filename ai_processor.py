import json
import logging
import re

import config
from ai_validator import AIValidator

logger = logging.getLogger(__name__)

_openai_client = None
_anthropic_client = None

if config.OPENAI_API_KEY:
    import openai
    _openai_client = openai.OpenAI(api_key=config.OPENAI_API_KEY)

if config.ANTHROPIC_API_KEY:
    import anthropic
    _anthropic_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

_validator = AIValidator()

# ---------------------------------------------------------------------------
# 프롬프트
# ---------------------------------------------------------------------------

_TAG_SYSTEM = """\
당신은 여행 콘텐츠 분석 전문가입니다.
주어진 장소 정보를 분석하여 아래 JSON 형식만 반환하세요. 다른 텍스트는 절대 포함하지 마세요.

{
  "ai_tags": {
    "themes":    ["자연","역사","문화","액티비티","힐링","음식","쇼핑" 중 해당하는 항목들],
    "mood":      ["조용한","활기찬","낭만적","가족적" 중 해당하는 항목들],
    "season":    ["봄","여름","가을","겨울" 중 추천 계절],
    "companion": ["혼자","커플","가족","친구" 중 해당하는 항목들]
  },
  "ai_summary": "장소의 핵심 특징과 추천 포인트를 담은 2~3문장 한국어 요약 (200자 이내)",
  "visit_role": "meal 또는 cafe 또는 spot 또는 culture 중 반드시 하나",
  "estimated_duration": 60,
  "visit_time_slot": ["breakfast","morning","lunch","afternoon","dinner","night" 중 해당하는 항목들]
}

visit_role 분류 기준:
  meal    = 식사 가능한 음식점/식당/레스토랑
  cafe    = 카페/디저트/음료 위주 (식사 대용 불가)
  spot    = 관광지/명소/레포츠/쇼핑 등 체험 장소
  culture = 박물관/미술관/문화시설

estimated_duration 기준 (단위: 분, 반드시 10 이상 240 이하 정수):
  meal=50~90, cafe=30~60, spot=60~120, culture=45~100
"""

_EMBED_MAX_CHARS = 8_000   # text-embedding-3-small 토큰 한도 대비 여유치


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict | None:
    """LLM 응답에서 첫 번째 JSON 객체만 추출한다. 실패 시 None 반환."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())

    # 1차 시도: 전체 파싱
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2차 시도: 첫 번째 { } 블록만 추출 (JSON 이후 텍스트 무시)
    try:
        start = text.index("{")
        depth, end = 0, -1
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end != -1:
            return json.loads(text[start:end + 1])
    except (ValueError, json.JSONDecodeError):
        pass

    return None


def _build_embed_text(place: dict) -> str:
    parts = [
        place.get("name", ""),
        place.get("region_1", ""),
        place.get("region_2", ""),
        place.get("overview", "") or "",
    ]
    return " ".join(p for p in parts if p).strip()[:_EMBED_MAX_CHARS]


# ---------------------------------------------------------------------------
# 공개 함수
# ---------------------------------------------------------------------------

def generate_tags_and_summary(place: dict) -> dict:
    """
    Anthropic Claude로 AI 태그/요약/역할/체류시간/시간대를 생성하고 검증한다.

    반환 키:
      ai_tags, ai_summary, visit_role, estimated_duration, visit_time_slot,
      ai_validation_status, ai_validation_errors
    """
    if _anthropic_client is None:
        raise RuntimeError("ANTHROPIC_API_KEY not set — tagging skipped")

    overview_snippet = (place.get("overview") or "")[:1_500]

    user_content = (
        f"장소명: {place.get('name', '')}\n"
        f"카테고리 코드: {place.get('category_id', '')}\n"
        f"지역: {place.get('region_1', '')} {place.get('region_2', '')}\n"
        f"설명: {overview_snippet}"
    )

    message = _anthropic_client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=600,
        system=_TAG_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = _extract_json(message.content[0].text)

    if raw is None:
        logger.warning("JSON parse failed for place_id=%s — applying fallback", place.get("place_id"))
        payload = {
            "ai_tags":            {},
            "ai_summary":         "",
            "visit_role":         None,
            "estimated_duration": None,
            "visit_time_slot":    [],
        }
    else:
        payload = {
            "ai_tags":            raw.get("ai_tags", {}),
            "ai_summary":         raw.get("ai_summary", ""),
            "visit_role":         raw.get("visit_role"),
            "estimated_duration": raw.get("estimated_duration"),
            "visit_time_slot":    raw.get("visit_time_slot", []),
        }

    return _validator.validate_place_payload(payload)


def generate_embedding(place: dict) -> list[float]:
    """OpenAI text-embedding-3-small으로 1536차원 벡터를 생성한다."""
    if _openai_client is None:
        raise RuntimeError("OPENAI_API_KEY not set — embedding skipped")

    text = _build_embed_text(place)
    if not text:
        raise ValueError(f"Cannot embed empty text for place: {place.get('tourapi_content_id')}")

    response = _openai_client.embeddings.create(
        input=text,
        model=config.OPENAI_EMBEDDING_MODEL,
    )
    return response.data[0].embedding


def process_place(place: dict) -> dict:
    """태깅·요약·검증·임베딩을 순차 실행한다."""
    ai_result = generate_tags_and_summary(place)
    ai_result["embedding"] = generate_embedding(place)
    return ai_result
