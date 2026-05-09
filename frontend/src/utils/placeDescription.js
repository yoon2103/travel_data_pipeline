const ROLE_LABELS = {
  cafe: '카페',
  meal: '식사 장소',
  spot: '관광지',
  culture: '문화 공간',
};

const MIN_USEFUL_DESCRIPTION_LENGTH = 34;

function normalizeText(value) {
  return typeof value === 'string' ? value.replace(/\s+/g, ' ').trim() : '';
}

function getRoleLabel(role) {
  return ROLE_LABELS[role] || '방문 장소';
}

function buildFallbackDescription(place, context = {}) {
  const name = normalizeText(place?.name) || '이 장소';
  const region = normalizeText(context.region);
  const role = place?.role || place?.visit_role || '';
  const roleLabel = getRoleLabel(role);
  const duration = normalizeText(place?.duration);
  const order = Number.isFinite(context.index) ? context.index + 1 : null;
  const routePosition = order ? `코스의 ${order}번째 지점` : '코스 중간 지점';
  const regionPhrase = region ? `${region} 일정에서 ` : '';
  const stayPhrase = duration ? ` 예상 체류 시간은 ${duration}입니다.` : '';

  if (role === 'cafe') {
    return `${name}는 ${regionPhrase}${routePosition}으로 배치된 카페입니다. 앞뒤 일정 사이에 잠시 쉬어가며 동선을 정리하기 좋은 휴식 지점입니다.${stayPhrase}`;
  }
  if (role === 'meal') {
    return `${name}는 ${regionPhrase}${routePosition}으로 배치된 식사 장소입니다. 이동 흐름을 크게 벗어나지 않으면서 식사 시간을 채우기 위한 지점으로 구성했습니다.${stayPhrase}`;
  }
  if (role === 'culture') {
    return `${name}는 ${regionPhrase}${routePosition}으로 배치된 문화 공간입니다. 주변 일정과 함께 묶어 둘러보기 좋도록 코스 흐름 안에 포함했습니다.${stayPhrase}`;
  }
  if (role === 'spot') {
    return `${name}는 ${regionPhrase}${routePosition}으로 배치된 관광지입니다. 앞뒤 장소와의 이동 흐름을 고려해 당일 코스의 주요 방문 지점으로 구성했습니다.${stayPhrase}`;
  }

  return `${name}는 ${regionPhrase}${routePosition}으로 배치된 ${roleLabel}입니다. 앞뒤 일정과의 이동 흐름을 고려해 당일 코스 안에 포함했습니다.${stayPhrase}`;
}

export function getDisplayPlaceDescription(place, context = {}) {
  const original = normalizeText(place?.description || place?.overview);
  if (original.length >= MIN_USEFUL_DESCRIPTION_LENGTH) {
    return original;
  }

  const fallback = buildFallbackDescription(place, context);
  if (!original) return fallback;

  return `${original} ${fallback}`;
}
