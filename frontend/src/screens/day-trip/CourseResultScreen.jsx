import { useState, useEffect } from 'react';
import { MOOD_TO_THEMES } from '../../data/dayTripDummyData';
import { useRef } from 'react';
import { getDisplayPlaceDescription } from '../../utils/placeDescription';
import { saveCourseToLocalStorage } from '../../utils/savedCourses';
import { trackEvent, courseTelemetryContext } from '../../utils/telemetry';

let _addPlaceCounter = 0;

/* ─── SVG 아이콘 ──────────────────────────────────── */
const BackIcon = () => ( <svg width="24" height="24" viewBox="0 0 24 24" fill="none"> <path d="M15 18l-6-6 6-6" stroke="#111827" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/> </svg> );
const ShareIcon = () => ( <svg width="20" height="20" viewBox="0 0 24 24" fill="none"> <path d="M8.5 14.5L15.5 17.5M15.5 6.5L8.5 9.5M21 5C21 6.65685 19.6569 8 18 8C16.3431 8 15 6.65685 15 5C15 3.34315 16.3431 2 18 2C19.6569 2 21 3.34315 21 5ZM9 12C9 13.6569 7.65685 15 6 15C4.34315 15 3 13.6569 3 12C3 10.3431 4.34315 9 6 9C7.65685 9 9 10.3431 9 12ZM21 19C21 20.6569 19.6569 22 18 22C16.3431 22 15 20.6569 15 19C15 17.3431 16.3431 16 18 16C19.6569 16 21 17.3431 21 19Z" stroke="#4B5563" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/> </svg> );
const CarIcon = () => ( <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.8l-1.4 2.9A3.7 3.7 0 002 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/></svg> );
const ChevronIcon = ({ isOpen }) => ( <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style={{ transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}> <path d="M6 9l6 6 6-6" stroke="#9CA3AF" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/> </svg> );
const DragHandleIcon = () => ( <svg width="20" height="20" viewBox="0 0 24 24" fill="none"> <path d="M4 8h16M4 16h16" stroke="#CBD5E1" strokeWidth="2.5" strokeLinecap="round"/> </svg> );
const PlusIcon = ({ size = 14, color = "#2563EB" }) => ( <svg width={size} height={size} viewBox="0 0 24 24" fill="none"> <path d="M12 5v14M5 12h14" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/> </svg> );
const CheckIcon = ({ size = 14, color = "#2563EB" }) => ( <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5"/></svg> );
const CloseIcon = () => ( <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6L6 18M6 6l12 12"/></svg> );
const StarIcon = () => ( <svg width="12" height="12" viewBox="0 0 24 24" fill="#F59E0B"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg> );
const InfoIcon = () => ( <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#60A5FA" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg> );
const ClockIcon = () => ( <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg> );
const MapPinIcon = () => ( <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 1118 0z"/><circle cx="12" cy="10" r="3"/></svg> );
const WarnIcon = () => ( <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> );

const AUTO_DEPARTURE_TIME = '내일 09:00';
const LATE_DEFAULT_DEPARTURE_HOUR = 20;
const TIME_BAND_TO_TIME = {
  morning: '09:00',
  daytime: '12:00',
  evening: '17:00',
};

function getMappedDepartureTime(params) {
  if (params?.mapped_departure_time) return params.mapped_departure_time;
  if (params?.departure_time) return params.departure_time;
  const bandTime = TIME_BAND_TO_TIME[params?.selected_time_band] || TIME_BAND_TO_TIME.daytime;
  return `오늘 ${bandTime}`;
}

function getAutoDeparturePayloadTime() {
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const yyyy = tomorrow.getFullYear();
  const mm = String(tomorrow.getMonth() + 1).padStart(2, '0');
  const dd = String(tomorrow.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd} 09:00`;
}

function isLateDefaultDepartureTime(value) {
  const match = String(value || '').match(/^오늘\s+(\d{1,2}):(\d{2})/);
  return match ? Number(match[1]) >= LATE_DEFAULT_DEPARTURE_HOUR : false;
}

function getDepartureHour(value) {
  const match = String(value || '').match(/(\d{1,2}):(\d{2})/);
  return match ? Number(match[1]) : null;
}

function isNightFriendlyParams(params) {
  const hour = getDepartureHour(params?.departure_time);
  if (params?.euljiro_night_mode_removed) return false;
  if (params?.time_band_night_friendly) return true;
  if (hour == null || hour < 18) return false;
  const text = [
    params?.start_anchor,
    params?.selectedAnchor,
    params?.selected_anchor,
    params?.start_anchor_label,
    params?.selected_anchor_vibe,
    params?.anchor_theme_seed,
    params?.mood,
    params?.theme,
  ].filter(Boolean).join(' ').toLowerCase();
  return /야간|야경|노포|을지로|힙지로|광안리\s*야경|익선|데이트|한남|감성|night|nightlife|nightview|date/.test(text);
}

function getLateTimeSoftNotice(params) {
  if (!params?.departure_time_user_selected) return null;
  const selectedHour = getDepartureHour(params?.departure_time);
  if (selectedHour == null || selectedHour < 18) return null;
  if (isNightFriendlyParams(params)) return null;
  return '늦은 시간에는 일부 장소의 영업이 종료되었을 수 있어요. 산책·야경·식사 중심으로 더 안정적인 코스를 추천해드릴게요.';
}

function getGenerationDepartureTime(params) {
  if (params?.selected_time_band || params?.mapped_departure_time) {
    return getMappedDepartureTime(params);
  }
  if (params?.departure_time_user_selected) {
    const selectedHour = getDepartureHour(params?.departure_time);
    if (selectedHour != null && selectedHour >= 22 && !isNightFriendlyParams(params)) {
      return getAutoDeparturePayloadTime();
    }
    return params?.departure_time ?? getAutoDeparturePayloadTime();
  }
  if (!params?.departure_time || params.departure_time === AUTO_DEPARTURE_TIME || isLateDefaultDepartureTime(params.departure_time)) {
    return getAutoDeparturePayloadTime();
  }
  return params.departure_time;
}

function getSafeAlternateTheme(params) {
  const currentTheme = String(params?.theme || '').toLowerCase();
  const currentMood = String(params?.mood || '').toLowerCase();
  const anchorText = `${params?.start_anchor || ''} ${params?.selectedAnchor || ''} ${params?.selected_anchor_vibe || ''}`.toLowerCase();
  if (currentTheme !== 'default') return 'default';
  if (/카페|cafe|성수|한남/.test(anchorText + currentMood)) return 'cafe';
  if (/북촌|익선|전주|진주|역사|한옥|history/.test(anchorText + currentMood)) return 'history';
  if (/광안|을지로|야경|night/.test(anchorText + currentMood)) return 'night';
  return 'walk';
}

/* ─── API 응답 → UI 포맷 변환 ──────────────────────── */
function normalizePlace(p) {
  const durationMin = (() => {
    if (!p.scheduled_start || !p.scheduled_end) return 60;
    const [sh, sm] = p.scheduled_start.split(':').map(Number);
    const [eh, em] = p.scheduled_end.split(':').map(Number);
    return (eh * 60 + em) - (sh * 60 + sm);
  })();
  const durationLabel = durationMin >= 60
    ? `${Math.floor(durationMin / 60)}시간${durationMin % 60 ? ` ${durationMin % 60}분` : ''}`
    : `${durationMin}분`;

  return {
    id:           String(p.place_id ?? p.order),
    place_id:     p.place_id ?? null,
    time:         p.scheduled_start ?? '—',
    endTime:      p.scheduled_end ?? null,
    name:         p.name,
    duration:     durationLabel,
    duration_min: durationMin,
    role:         p.visit_role,
    address:      '',
    description:  p.description || '',
    image:        p.first_image_url || null,
    placeholderUsed: p.placeholder_used ?? !p.first_image_url,
    lat:          p.latitude ?? null,
    lon:          p.longitude ?? null,
    transit:      p.move_minutes_from_prev != null ? `약 ${p.move_minutes_from_prev}분 이동` : null,
  };
}

/* ─── 후보 API 응답 → UI 포맷 변환 ──────────────────── */
function normalizeCandidate(c) {
  const pid = c.place_id ?? c.id;
  return {
    id:       String(pid),
    place_id: pid,
    name:     c.name,
    category: c.visit_role || c.category || '',
    transit:  c.travel_minutes != null ? `도보 ${c.travel_minutes}분` : (c.transit || ''),
    rating:   c.rating ?? null,
    reviews:  c.review_count ?? c.reviews ?? null,
    address:  c.address || '',
    image:    c.first_image_url || null,
    placeholderUsed: c.placeholder_used ?? !c.first_image_url,
    lat:      c.latitude ?? null,
    lon:      c.longitude ?? null,
  };
}

const PLACEHOLDER_META = {
  cafe: {
    label: '카페 이미지 준비 중',
    icon: '☕',
    className: 'from-[#F8EFE6] via-[#EED8C2] to-[#D7B08A] text-[#6F421F]',
  },
  meal: {
    label: '식사 이미지 준비 중',
    icon: '🍽️',
    className: 'from-[#FFE7D6] via-[#FFD3BD] to-[#F8A879] text-[#8A3F19]',
  },
  history: {
    label: '문화 이미지 준비 중',
    icon: '⌂',
    className: 'from-[#EFE7D4] via-[#E4D5B8] to-[#C9AA7D] text-[#6D4D25]',
  },
  night: {
    label: '야경 이미지 준비 중',
    icon: '✦',
    className: 'from-[#1F2A44] via-[#293A63] to-[#4C5F93] text-white',
  },
  sea: {
    label: '바다 이미지 준비 중',
    icon: '≈',
    className: 'from-[#D8F1F5] via-[#BFE4EC] to-[#80BCCE] text-[#155E75]',
  },
  default: {
    label: '장소 이미지 준비 중',
    icon: '⌖',
    className: 'from-[#EEF2F7] via-[#E2E8F0] to-[#CBD5E1] text-[#475569]',
  },
};

const CAFE_PLACEHOLDER_VARIANTS = [
  'from-[#F8EFE6] via-[#EED8C2] to-[#D7B08A] text-[#6F421F]',
  'from-[#F6EBDD] via-[#E7C9AA] to-[#C99568] text-[#653B1B]',
  'from-[#F3E7DC] via-[#DEC2AD] to-[#B98D72] text-[#5F3C2C]',
];

const getStableVariantIndex = (value = '', total = 1) => {
  const text = String(value || '');
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) % 9973;
  }
  return Math.abs(hash) % total;
};

const resolvePlaceholderMeta = (place = {}, params = {}) => {
  const role = place.role || place.category || '';
  const moodText = `${params?.mood || ''} ${params?.theme || ''} ${params?.anchor_theme_seed || ''} ${params?.displayRegion || params?.region || ''}`;
  if (role === 'cafe' || /카페|cafe/i.test(moodText)) return PLACEHOLDER_META.cafe;
  if (role === 'meal' || /맛집|food|meal/i.test(moodText)) return PLACEHOLDER_META.meal;
  if (/야경|night/i.test(moodText)) return PLACEHOLDER_META.night;
  if (/바다|해변|오션|sea|beach|여수|목포|포항|강릉|속초|광안리|애월/i.test(moodText)) return PLACEHOLDER_META.sea;
  if (/역사|한옥|북촌|익선|history|문화/i.test(moodText)) return PLACEHOLDER_META.history;
  return PLACEHOLDER_META.default;
};

// Image-missing cafe cards must stay abstract. Do not use fake cafe photos or unapproved stock images here.
const PlaceholderVisual = ({ place, params, size = 'sm', className = '' }) => {
  const meta = resolvePlaceholderMeta(place, params);
  const isCafe = meta === PLACEHOLDER_META.cafe;
  const cafeVariant = CAFE_PLACEHOLDER_VARIANTS[getStableVariantIndex(place?.id || place?.name, CAFE_PLACEHOLDER_VARIANTS.length)];
  const paletteClass = isCafe ? cafeVariant : meta.className;
  const sizeClass = size === 'lg'
    ? 'w-full min-h-[150px] rounded-[16px]'
    : size === 'md'
      ? 'w-[72px] h-[72px] rounded-2xl'
      : 'w-[60px] h-[60px] rounded-[14px]';
  const iconClass = size === 'lg' ? 'text-[30px]' : size === 'md' ? 'text-[22px]' : 'text-[18px]';
  const iconShellClass = isCafe
    ? size === 'lg'
      ? 'w-[54px] h-[54px] rounded-[18px] bg-white/45 shadow-sm ring-1 ring-white/40'
      : size === 'md'
        ? 'w-[42px] h-[42px] rounded-[15px] bg-white/45 shadow-sm ring-1 ring-white/40'
        : 'w-[34px] h-[34px] rounded-[12px] bg-white/45 shadow-sm ring-1 ring-white/40'
    : '';
  return (
    <div
      className={`${sizeClass} relative overflow-hidden bg-gradient-to-br ${paletteClass} flex flex-col items-center justify-center shrink-0 shadow-inner ${className}`}
      aria-label={meta.label}
      data-placeholder-used="true"
      data-placeholder-type={meta.label}
    >
      {isCafe && (
        <>
          <span
            className="absolute inset-0 opacity-[0.2]"
            style={{
              backgroundImage: 'linear-gradient(135deg, rgba(255,255,255,0.65) 1px, transparent 1px)',
              backgroundSize: '11px 11px',
            }}
            aria-hidden="true"
          />
          <span className="absolute left-2 right-2 bottom-2 h-[1px] bg-white/45" aria-hidden="true" />
          <span className="absolute left-3 right-5 bottom-4 h-[1px] bg-[#8B5A2B]/15" aria-hidden="true" />
        </>
      )}
      <span className={`${iconShellClass} relative flex items-center justify-center`} aria-hidden="true">
        <span className={`${iconClass} leading-none`}>{meta.icon}</span>
      </span>
      {size === 'lg' && <span className="relative mt-2 text-[12px] font-bold opacity-80">{isCafe ? '카페 이미지 준비 중' : '대표 이미지 준비 중'}</span>}
    </div>
  );
};

const ResultMotionStyles = () => (
  <style>{`
@keyframes courseSoftIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes routeShimmer {
  0% { transform: translateX(-120%); }
  100% { transform: translateX(120%); }
}
.course-soft-in {
  animation: courseSoftIn 220ms ease-out both;
}
.route-skeleton-shimmer::after {
  content: "";
  position: absolute;
  inset: 0;
  transform: translateX(-120%);
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.62), transparent);
  animation: routeShimmer 1.25s ease-in-out infinite;
}
  `}</style>
);

const ROLE_LABEL = {
  cafe:    '분위기 좋은 카페',
  meal:    '인기 맛집',
  spot:    '대표 관광지',
  culture: '문화/전시 공간',
};

const CHANGE_LABEL = {
  meal: '다른 식당 보기',
  cafe: '다른 카페 보기',
  spot: '비슷한 장소로 바꾸기',
};

const SHEET_TITLE = {
  meal: '식당 변경',
  cafe: '카페 변경',
  spot: '장소 교체',
};

const ERROR_CLASS = {
  INPUT_PENDING: 'input_pending',
  EMPTY_CANDIDATE: 'empty_candidate',
  TIME_RESTRICT: 'time_restriction',
  RADIUS_RESTRICT: 'radius_restriction',
  API_TRANSIENT: 'api_transient',
  SERVER_ERROR: 'server_error',
  VALIDATION_INPUT: 'validation_input',
  UNKNOWN: 'unknown',
};

const ERROR_CLASS_LABEL = {
  [ERROR_CLASS.INPUT_PENDING]: 'INPUT_PENDING',
  [ERROR_CLASS.EMPTY_CANDIDATE]: 'EMPTY_CANDIDATE',
  [ERROR_CLASS.TIME_RESTRICT]: 'TIME_RESTRICT',
  [ERROR_CLASS.RADIUS_RESTRICT]: 'RADIUS_RESTRICT',
  [ERROR_CLASS.API_TRANSIENT]: 'API_TRANSIENT',
  [ERROR_CLASS.SERVER_ERROR]: 'SERVER_ERROR',
  [ERROR_CLASS.VALIDATION_INPUT]: 'VALIDATION_INPUT',
  [ERROR_CLASS.UNKNOWN]: 'UNKNOWN',
};

const ERROR_FAMILY = {
  CANDIDATE: 'candidate_coverage',
  TIME_WINDOW: 'time_window',
  POLICY_GUARD: 'policy_guard',
  SERVICE_ERROR: 'service_error',
  INPUT_ERROR: 'input_error',
  UNKNOWN: 'unknown',
};

const ERROR_STATE_META = {
  [ERROR_CLASS.INPUT_PENDING]: {
    family: ERROR_FAMILY.UNKNOWN,
    domain: 'generation_flow',
    actionIntent: 'retry',
    canSplit: false,
  },
  [ERROR_CLASS.EMPTY_CANDIDATE]: {
    family: ERROR_FAMILY.CANDIDATE,
    domain: 'candidate_fetch',
    actionIntent: 'adjust_conditions',
    canSplit: true,
  },
  [ERROR_CLASS.TIME_RESTRICT]: {
    family: ERROR_FAMILY.TIME_WINDOW,
    domain: 'temporal_filter',
    actionIntent: 'adjust_time',
    canSplit: true,
  },
  [ERROR_CLASS.RADIUS_RESTRICT]: {
    family: ERROR_FAMILY.POLICY_GUARD,
    domain: 'coverage_policy',
    actionIntent: 'adjust_condition',
    canSplit: true,
  },
  [ERROR_CLASS.API_TRANSIENT]: {
    family: ERROR_FAMILY.SERVICE_ERROR,
    domain: 'service_transport',
    actionIntent: 'retry',
    canSplit: false,
  },
  [ERROR_CLASS.SERVER_ERROR]: {
    family: ERROR_FAMILY.SERVICE_ERROR,
    domain: 'server_error',
    actionIntent: 'retry',
    canSplit: false,
  },
  [ERROR_CLASS.VALIDATION_INPUT]: {
    family: ERROR_FAMILY.INPUT_ERROR,
    domain: 'request_contract',
    actionIntent: 'adjust_input',
    canSplit: true,
  },
  [ERROR_CLASS.UNKNOWN]: {
    family: ERROR_FAMILY.UNKNOWN,
    domain: 'unclassified',
    actionIntent: 'retry',
    canSplit: false,
  },
};

const ERROR_PRESENTATION = {
  [ERROR_CLASS.INPUT_PENDING]: {
    title: '코스 카드가 아직 안 보였어요',
    message: '지금 막 준비 중이에요. 잠깐만 기다리면 이어서 보여드릴게요.',
    hints: ['잠깐만 더 기다려 주세요.', '다시 눌러서 이어서 확인해 보세요.'],
    buttonLabel: '다시 이어보기',
    actionTarget: undefined,
    action: 'retry',
    stateTag: ERROR_CLASS_LABEL[ERROR_CLASS.INPUT_PENDING],
  },
  [ERROR_CLASS.EMPTY_CANDIDATE]: {
    title: '조금 더 많은 후보를 찾아볼게요',
    message: '지금 시간 기준으로는 열려 있는 후보가 적어요. 출발 시간을 내일 오전으로 바꾸면 더 좋은 코스를 추천할 수 있어요.',
    hints: ['다른 분위기로 다시 만들어 보세요.', '필요하면 조건 화면에서 출발 시간을 바꿔 보세요.', '출발지나 지역을 바꾸면 후보가 더 넓어질 수 있어요.'],
    buttonLabel: '다른 분위기 추천',
    secondaryButtonLabel: '조건 바꿔 다시 보기',
    secondaryAction: 'adjust',
    secondaryActionTarget: 'condition',
    actionTarget: 'mood_or_condition',
    action: 'adjust',
    stateTag: ERROR_CLASS_LABEL[ERROR_CLASS.EMPTY_CANDIDATE],
  },
  [ERROR_CLASS.TIME_RESTRICT]: {
    title: '밤 시간대엔 추천이 조금 적을 수 있어요',
    message: '현재 시간대는 영업이 끝난 곳이 많아 후보가 줄어들기 쉬워요. 출발 시간을 1~2시간 앞당기면 더 많은 후보를 볼 수 있어요.',
    hints: ['1~2시간 정도 일찍 시작해 보세요.', '오전/오후 기준으로 시간대를 바꿔 보세요.', '지역이나 테마도 함께 바꿔보면 더 좋아져요.'],
    buttonLabel: '시간대 변경 후 다시 보기',
    secondaryButtonLabel: '조건 변경하기',
    secondaryAction: 'adjust',
    secondaryActionTarget: 'condition',
    actionTarget: 'time',
    action: 'adjust',
    stateTag: ERROR_CLASS_LABEL[ERROR_CLASS.TIME_RESTRICT],
  },
  [ERROR_CLASS.RADIUS_RESTRICT]: {
    title: '지금 조합은 후보가 부족해요',
    message: '출발지와 시간, 테마 조건이 맞물려 후보가 충분히 모이지 않았어요. 조건을 살짝 조정하면 다양한 코스가 다시 보입니다.',
    hints: ['시간을 1~2시간 앞당겨 보세요.', '출발지/지역을 바꿔 보세요.', '다른 분위기나 테마를 바꿔 보세요.'],
    buttonLabel: '조건 변경하기',
    secondaryButtonLabel: '시간대 변경하기',
    secondaryAction: 'adjust',
    secondaryActionTarget: 'time',
    actionTarget: 'condition',
    action: 'adjust',
    stateTag: ERROR_CLASS_LABEL[ERROR_CLASS.RADIUS_RESTRICT],
  },
  [ERROR_CLASS.API_TRANSIENT]: {
    title: '조금만 쉬었다 다시 볼게요',
    message: '지금 잠깐 신호가 느려서 이어지는 데 시간이 걸렸어요. 한 번만 더 눌러주시면 바로 다시 시도할게요.',
    hints: ['조금 뒤에 다시 눌러 주세요.', '잠시 후 다시 눌러 보세요.'],
    buttonLabel: '다시 이어보기',
    actionTarget: 'api',
    action: 'retry',
    stateTag: ERROR_CLASS_LABEL[ERROR_CLASS.API_TRANSIENT],
  },
  [ERROR_CLASS.SERVER_ERROR]: {
    title: '잠깐만 더 기다려 주세요',
    message: '잠시 연결이 느려서 잠깐 멈췄어요. 잠시 뒤 한 번만 다시 눌러주시면 이어서 보여드릴게요.',
    hints: ['잠시 뒤에 다시 눌러 주세요.', '한 번 더 눌러 보세요.'],
    buttonLabel: '잠시 후 이어보기',
    actionTarget: 'api',
    action: 'retry',
    stateTag: ERROR_CLASS_LABEL[ERROR_CLASS.SERVER_ERROR],
  },
  [ERROR_CLASS.VALIDATION_INPUT]: {
    title: '선택값이 덜 채워졌어요',
    message: '선택한 값이 서로 안 맞아서 추천이 막혔어요. 값만 다시 맞춰주면 바로 이어져요.',
    hints: ['조건을 다시 선택해 주세요.', '처음부터 다시 시작해 보세요.'],
    buttonLabel: '조건 바꿔 다시 보기',
    actionTarget: 'condition',
    action: 'adjust',
    stateTag: ERROR_CLASS_LABEL[ERROR_CLASS.VALIDATION_INPUT],
  },
  [ERROR_CLASS.UNKNOWN]: {
    title: '조금 더 기다려야 할 때예요',
    message: '지금은 잠깐 멈춘 순간이 있어요. 다시 눌러주면 이어서 보여드릴게요.',
    hints: ['다시 이어보기 버튼으로 한 번 더 눌러 주세요.'],
    buttonLabel: '다시 이어보기',
    action: 'retry',
    stateTag: ERROR_CLASS_LABEL[ERROR_CLASS.UNKNOWN],
  },
};

const resolveCourseErrorClass = (input) => {
  if (!input) {
    return {
      errorClass: ERROR_CLASS.INPUT_PENDING,
      source: 'frontend_input_state',
    };
  }

  const rawCode = String(input.errorCode || input.code || '').toUpperCase();
  const rawMessage = String(input.message || input.error || '').toLowerCase();
  const status = Number(input.status);

  if (rawCode === 'NO_COURSE_ALL_RADIUS' || rawMessage.includes('no_course_all_radius') || rawMessage.includes('places=')) {
    return {
      errorClass: ERROR_CLASS.EMPTY_CANDIDATE,
      source: 'backend_course_empty',
    };
  }

  if (
    rawMessage.includes('영업') || rawMessage.includes('운영') || rawMessage.includes('영업시간') ||
    rawMessage.includes('마감') || rawMessage.includes('open') || rawMessage.includes('close time') ||
    rawMessage.includes('late-night') || rawMessage.includes('late night') || rawMessage.includes('close')
  ) {
    return {
      errorClass: ERROR_CLASS.TIME_RESTRICT,
      source: 'backend_time_policy',
    };
  }

  if (
    rawMessage.includes('25km') ||
    rawMessage.includes('25km까지') ||
    rawMessage.includes('확장해도') ||
    rawMessage.includes('생성할 수 없습니다') ||
    rawMessage.includes('25km까지 확장해도 코스를 생성할 수 없습니다')
  ) {
    return {
      errorClass: ERROR_CLASS.RADIUS_RESTRICT,
      source: 'backend_radius_policy',
    };
  }

  if (status >= 500 && status < 600) {
    return {
      errorClass: ERROR_CLASS.SERVER_ERROR,
      source: 'backend_http_5xx',
    };
  }

  if (
    rawMessage.includes('system') ||
    rawMessage.includes('server') ||
    rawMessage.includes('backend') ||
    rawMessage.includes('service') ||
    rawMessage.includes('internal error') ||
    rawMessage.includes('internal') ||
    rawMessage.includes('error') ||
    rawMessage.includes('요청이 처리되지') ||
    rawMessage.includes('요청을 처리하지') ||
    rawMessage.includes('처리 중 오류') ||
    rawMessage.includes('일시적')
  ) {
    return {
      errorClass: ERROR_CLASS.API_TRANSIENT,
      source: 'backend_service_error',
    };
  }

  if (status === 400 || status === 422 || rawMessage.includes('invalid') || rawMessage.includes('요청') || rawMessage.includes('required')) {
    return {
      errorClass: ERROR_CLASS.VALIDATION_INPUT,
      source: 'frontend_validation',
    };
  }

  return {
    errorClass: ERROR_CLASS.UNKNOWN,
    source: 'generic_fallback',
  };
};

const getFriendlyErrorMessage = (input, context = {}) => {
  const { errorClass, source } = resolveCourseErrorClass(input);
  const base = ERROR_PRESENTATION[errorClass] || ERROR_PRESENTATION[ERROR_CLASS.UNKNOWN];
  const meta = ERROR_STATE_META[errorClass] || ERROR_STATE_META[ERROR_CLASS.UNKNOWN];
  const presentation = context.nightFriendly && errorClass === ERROR_CLASS.EMPTY_CANDIDATE
    ? {
        ...base,
        message: '야간에 어울리는 후보를 조금 더 찾아볼게요. 노포, 야경, 산책 중심으로 다시 추천해 볼 수 있어요.',
        hints: ['야경과 산책 중심으로 다시 만들어 보세요.', '조건 변경하기에서 시간을 조금 앞당길 수도 있어요.', '다른 분위기 추천으로 야간 후보를 다시 넓혀볼게요.'],
      }
    : base;

  return {
    ...presentation,
    errorClass,
    errorClassLabel: ERROR_CLASS_LABEL[errorClass] || ERROR_CLASS_LABEL[ERROR_CLASS.UNKNOWN],
    source,
    errorFamily: meta.family,
    errorDomain: meta.domain,
    errorActionIntent: meta.actionIntent,
    canBeSplit: meta.canSplit,
  };
};
export default function CourseResultScreen({ onBack, onSave, onRemakeMood, params }) {
  // ── API 상태 ──
  const [loading, setLoading]     = useState(true);
  const [apiError, setApiError]   = useState(null);
  const [courseId, setCourseId]               = useState(null);
  const [courseDesc, setCourseDesc]           = useState(null);
  const [missingSlotReason, setMissingSlotReason] = useState(null);
  const [optionNotice, setOptionNotice]           = useState(null);
  const [totalDuration, setTotalDuration]     = useState(null);
  const [totalTravel, setTotalTravel]         = useState(null);
  const [regionStatus, setRegionStatus]       = useState(null);

  // ── 핵심 상태값 ──
  const [mode, setMode]                           = useState('view');
  const [hasAddedPlace, setHasAddedPlace]         = useState(false);
  const [hasPendingRecalculate, setHasPendingRecalculate] = useState(false);
  const [selectedTargetPlace, setSelectedTargetPlace]     = useState(null);
  const [places, setPlaces]                       = useState([]);

  // ── 후보 상태 ──
  const [candidates, setCandidates]           = useState([]);
  const [candidateLoading, setCandidateLoading] = useState(false);
  const [saving, setSaving]                   = useState(false);

  // ── UI 보조 상태 ──
  const [expandedIds, setExpandedIds]   = useState([]);
  const [draggingIndex, setDraggingIndex] = useState(null);
  const [activeDragId, setActiveDragId]   = useState(null);
  const [sheetMode, setSheetMode]           = useState(null);
  const [addTargetIndex, setAddTargetIndex] = useState(null);
  const [toastMessage, setToastMessage]     = useState(null);
  const [regeneratePending, setRegeneratePending] = useState(false);
  const regenerateTimerRef = useRef(null);

  const bottomNavOffset = 'calc(84px + env(safe-area-inset-bottom, 0px))';
  const resultListBottomPadding = mode === 'edit'
    ? 'calc(430px + env(safe-area-inset-bottom, 0px))'
    : 'calc(340px + env(safe-area-inset-bottom, 0px))';
  const manualEditTravelTimeLimit = 180;
  const manualEditTravelWarning = mode === 'edit'
    && !hasPendingRecalculate
    && totalTravel != null
    && totalTravel > 108
    && totalTravel <= manualEditTravelTimeLimit;

  const buildRouteMetrics = (dataOrPlaces) => {
    const sourcePlaces = Array.isArray(dataOrPlaces) ? dataOrPlaces : (dataOrPlaces?.places || []);
    const trace = Array.isArray(dataOrPlaces) ? null : (dataOrPlaces?.recommendation_trace || {});
    const route = trace?.route_coherence || {};
    return {
      place_count: sourcePlaces.length,
      route_coherence_score: route.route_coherence_score ?? trace?.route_coherence_score ?? null,
      route_purity_score: route.route_purity_score ?? trace?.route_purity_score ?? null,
      image_missing_count: sourcePlaces.filter((p) => !(p.first_image_url || p.image)).length,
      first_image_available: Boolean(sourcePlaces[0]?.first_image_url || sourcePlaces[0]?.image),
    };
  };

  const trackCourseEvent = (eventType, extraContext = {}, routeMetrics = {}) => {
    trackEvent(eventType, {
      ...courseTelemetryContext(params || {}),
      screen: 'result',
      ...extraContext,
    }, routeMetrics);
  };

  useEffect(() => () => {
    if (regenerateTimerRef.current) {
      window.clearTimeout(regenerateTimerRef.current);
    }
  }, []);

  const handleRemakeMoodClick = () => {
    if (regeneratePending) return;
    setRegeneratePending(true);
    trackCourseEvent('regenerate_clicked', { action: 'different_mood' }, buildRouteMetrics(places));
    trackCourseEvent('regenerate_after_result', { action: 'different_mood' }, buildRouteMetrics(places));
    regenerateTimerRef.current = window.setTimeout(() => {
      onRemakeMood?.();
    }, 420);
  };

  // ── API 호출 ──
  useEffect(() => {
    if (!params) return;
    const themes = MOOD_TO_THEMES[params.mood] ?? [];

    const DENSITY_TO_TEMPLATE = { '여유롭게': 'light', '적당히': 'standard', '알차게': 'full' };
    const template = DENSITY_TO_TEMPLATE[params.density] ?? params.template ?? 'standard';

    const WALK_TO_RADIUS = { '적게': 5, '보통': 10, '조금 멀어도 좋아요': 18 };
    const walk_max_radius = WALK_TO_RADIUS[params.walk] ?? null;
    const selectedAnchorRaw = params.start_anchor || params.selectedAnchor || params.selected_anchor || null;
    const displayRegion = params.displayRegion || params.display_region || params.region || '';
    const intendedCity = params.intended_city || params.region || '';
    const queryRegion = params.query_region_1 || params.region || '';
    const movementOption = params.movement_option || params.movement || params.density || null;
    const theme = themes[0] || params.theme || params.mood || 'default';
    const defaultPresetMode = params.default_preset_mode !== false;
    const generationDepartureTime = getGenerationDepartureTime(params);
    const nightFriendlyMode = isNightFriendlyParams(params);
    const mobilePayloadDebug = {
      region: params.region,
      selected_anchor: selectedAnchorRaw,
      start_anchor: params.start_anchor ?? null,
      start_anchor_label: params.start_anchor_label ?? null,
      mood: params.mood ?? null,
      theme,
      departure_time: generationDepartureTime,
      requested_departure_time: params.departure_time ?? null,
      selected_time_band: params.selected_time_band ?? null,
      mapped_departure_time: params.mapped_departure_time ?? generationDepartureTime,
      departure_time_user_selected: !!params.departure_time_user_selected,
      movement_option: movementOption,
      time_option: params.time_option ?? null,
      zone_id: params.zone_id ?? null,
      start_lat: params.start_lat ?? null,
      start_lon: params.start_lon ?? null,
      default_preset_mode: defaultPresetMode,
      night_friendly_mode: nightFriendlyMode,
      euljiro_mood_label_applied: !!params.euljiro_mood_label_applied,
      euljiro_night_mode_removed: !!params.euljiro_night_mode_removed,
    };

    const payload = {
      region:              params.region,
      departure_time:      generationDepartureTime,
      selected_time_band:  params.selected_time_band ?? null,
      mapped_departure_time: params.mapped_departure_time ?? generationDepartureTime,
      time_band_night_friendly: !!params.time_band_night_friendly,
      departure_time_user_selected: !!params.departure_time_user_selected,
      query_region_1:      queryRegion,
      intended_city:       intendedCity,
      display_region:      displayRegion,
      displayRegion:       displayRegion,
      selected_anchor:     selectedAnchorRaw,
      selectedAnchor:      selectedAnchorRaw,
      start_anchor:        params.start_anchor ?? null,
      start_anchor_label:  params.start_anchor_label ?? null,
      start_lat:           params.start_lat ?? null,
      start_lon:           params.start_lon ?? null,
      zone_id:             params.zone_id ?? null,
      mood:                params.mood ?? null,
      theme,
      time_option:         params.time_option ?? null,
      movement_option:     movementOption,
      anchor_theme_seed:   params.anchor_theme_seed ?? null,
      anchor_district:     params.anchor_district ?? null,
      selected_anchor_vibe: params.selected_anchor_vibe ?? null,
      default_preset_mode: defaultPresetMode,
      night_friendly_mode: nightFriendlyMode,
      euljiro_mood_label_applied: !!params.euljiro_mood_label_applied,
      euljiro_night_mode_removed: !!params.euljiro_night_mode_removed,
      mobile_payload_debug: mobilePayloadDebug,
      themes,
      template,
      region_travel_type:  params.region_travel_type ?? 'urban',
      walk_max_radius,
    };
    console.log('[CourseGenerate] request payload:', payload);
    trackCourseEvent('course_generate_start', {
      theme,
      mood: params.mood ?? null,
      action: 'initial_generate',
    });

    fetch('/api/course/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(async res => {
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw {
            status: res.status,
            message: data?.error || data?.detail || '지금은 잠깐 바빠서 바로 못 보여드렸어요. 잠시 뒤에 다시 눌러보면 이어드릴 수 있어요.',
            error: data?.error,
            code: data?.error_code || data?.errorCode,
          };
        }
        if (data && (data.error || data.error_code)) {
          throw {
            status: 200,
            message: data.error || data.detail || '조건이 더 잘 맞는 조합을 찾아 바로 이어드릴게요.',
            error: data.error,
            code: data.error_code || data.errorCode,
          };
        }
        return data;
      })
      .then(data => {
        console.log('[CourseGenerate] response:', data);
        const normalized = (data.places || []).map(normalizePlace);
        console.log('[CourseGenerate] normalized places:', normalized);
        setCourseId(data.course_id ?? null);
        setCourseDesc(data.description ?? null);
        setMissingSlotReason(data.missing_slot_reason ?? null);
        setOptionNotice(getLateTimeSoftNotice(params) || data.option_notice || null);
        setTotalDuration(data.total_duration_min ?? null);
        setTotalTravel(data.total_travel_min ?? null);
        setRegionStatus(data.region_status ?? null);
        setPlaces(normalized);
        setExpandedIds(normalized.length > 0 ? [normalized[0].id] : []);
        setLoading(false);
        trackCourseEvent('course_generate_success', {
          success: true,
          theme,
        }, buildRouteMetrics(data));
      })
      .catch(err => {
        setApiError(getFriendlyErrorMessage(err, { nightFriendly: nightFriendlyMode }));
        setLoading(false);
        trackCourseEvent('course_generate_fail', {
          success: false,
          failure_code: err?.code || err?.error || err?.message || 'unknown',
          theme,
        });
      });
  }, [params]);

  const handleRetryCourse = (overrides = {}) => {
    const safeOverrides = overrides && typeof overrides === 'object' && !overrides.preventDefault ? overrides : {};
    const retryParams = { ...params, ...safeOverrides };
    trackCourseEvent('retry_clicked', { action: safeOverrides.retry_action || 'retry_course' });
    if (!params) {
      onBack?.();
      return;
    }
    setApiError(null);
    setLoading(true);
    setPlaces([]);
    setExpandedIds([]);
    setHasPendingRecalculate(false);
    const retryThemes = safeOverrides.theme ? [safeOverrides.theme] : (MOOD_TO_THEMES[retryParams.mood] ?? []);
    const retrySelectedAnchor = retryParams.start_anchor || retryParams.selectedAnchor || retryParams.selected_anchor || null;
    const retryMovementOption = retryParams.movement_option || retryParams.movement || retryParams.density || null;
    const retryTheme = safeOverrides.theme || retryThemes[0] || retryParams.theme || retryParams.mood || 'default';
    const retryDefaultPresetMode = retryParams.default_preset_mode !== false;
    const retryDepartureTime = getGenerationDepartureTime(retryParams);
    const retryNightFriendlyMode = isNightFriendlyParams(retryParams);
    const retryMobilePayloadDebug = {
      region: retryParams.region,
      selected_anchor: retrySelectedAnchor,
      start_anchor: retryParams.start_anchor ?? null,
      start_anchor_label: retryParams.start_anchor_label ?? null,
      mood: retryParams.mood ?? null,
      theme: retryTheme,
      departure_time: retryDepartureTime,
      requested_departure_time: retryParams.departure_time ?? null,
      selected_time_band: retryParams.selected_time_band ?? null,
      mapped_departure_time: retryParams.mapped_departure_time ?? retryDepartureTime,
      departure_time_user_selected: !!retryParams.departure_time_user_selected,
      movement_option: retryMovementOption,
      time_option: retryParams.time_option ?? null,
      zone_id: retryParams.zone_id ?? null,
      start_lat: retryParams.start_lat ?? null,
      start_lon: retryParams.start_lon ?? null,
      default_preset_mode: retryDefaultPresetMode,
      night_friendly_mode: retryNightFriendlyMode,
      euljiro_mood_label_applied: !!retryParams.euljiro_mood_label_applied,
      euljiro_night_mode_removed: !!retryParams.euljiro_night_mode_removed,
    };
    const retryPayload = {
      region: retryParams.region,
      departure_time: retryDepartureTime,
      selected_time_band: retryParams.selected_time_band ?? null,
      mapped_departure_time: retryParams.mapped_departure_time ?? retryDepartureTime,
      time_band_night_friendly: !!retryParams.time_band_night_friendly,
      departure_time_user_selected: !!retryParams.departure_time_user_selected,
      query_region_1: retryParams.query_region_1 || retryParams.region || '',
      intended_city: retryParams.intended_city || retryParams.region || '',
      display_region: retryParams.displayRegion || retryParams.display_region || retryParams.region || '',
      displayRegion: retryParams.displayRegion || retryParams.region || '',
      selected_anchor: retrySelectedAnchor,
      selectedAnchor: retrySelectedAnchor,
      start_anchor: retryParams.start_anchor ?? null,
      start_anchor_label: retryParams.start_anchor_label ?? null,
      start_lat: retryParams.start_lat ?? null,
      start_lon: retryParams.start_lon ?? null,
      zone_id: retryParams.zone_id ?? null,
      mood: retryParams.mood ?? null,
      theme: retryTheme,
      time_option: retryParams.time_option ?? null,
      movement_option: retryMovementOption,
      anchor_theme_seed: retryParams.anchor_theme_seed ?? null,
      anchor_district: retryParams.anchor_district ?? null,
      selected_anchor_vibe: retryParams.selected_anchor_vibe ?? null,
      default_preset_mode: retryDefaultPresetMode,
      night_friendly_mode: retryNightFriendlyMode,
      euljiro_mood_label_applied: !!retryParams.euljiro_mood_label_applied,
      euljiro_night_mode_removed: !!retryParams.euljiro_night_mode_removed,
      mobile_payload_debug: retryMobilePayloadDebug,
      themes: retryThemes,
      template: retryParams.template || 'standard',
      region_travel_type: retryParams.region_travel_type ?? 'urban',
      walk_max_radius: { '적게': 5, '보통': 10, '조금 멀어도 좋아요': 18 }[retryParams.walk] ?? null,
    };
    trackCourseEvent('course_generate_start', {
      theme: retryTheme,
      mood: retryParams.mood ?? null,
      action: safeOverrides.retry_action || 'retry_generate',
    });

    fetch('/api/course/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(retryPayload),
    })
      .then(async res => {
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw {
            status: res.status,
            message: data?.error || data?.detail || '조금 더 쉬었다가 다시 눌러보면 바로 이어볼 수 있어요.',
            error: data?.error,
            code: data?.error_code || data?.errorCode,
          };
        }
        if (data && (data.error || data.error_code)) {
          throw {
            status: 200,
            message: data.error || data.detail || '조건이 더 잘 맞는 조합을 찾아 바로 이어 보여드릴게요.',
            error: data.error,
            code: data.error_code || data.errorCode,
          };
        }
        return data;
      })
      .then(data => {
        const normalized = (data.places || []).map(normalizePlace);
        setCourseId(data.course_id ?? null);
        setCourseDesc(data.description ?? null);
        setMissingSlotReason(data.missing_slot_reason ?? null);
        setOptionNotice(getLateTimeSoftNotice(retryParams) || data.option_notice || null);
        setTotalDuration(data.total_duration_min ?? null);
        setTotalTravel(data.total_travel_min ?? null);
        setRegionStatus(data.region_status ?? null);
        setPlaces(normalized);
        setExpandedIds(normalized.length > 0 ? [normalized[0].id] : []);
        setLoading(false);
        trackCourseEvent('course_generate_success', {
          success: true,
          theme: retryTheme,
        }, buildRouteMetrics(data));
      })
      .catch(err => {
        setApiError(getFriendlyErrorMessage(err, { nightFriendly: retryNightFriendlyMode }));
        setLoading(false);
        trackCourseEvent('course_generate_fail', {
          success: false,
          failure_code: err?.code || err?.error || err?.message || 'unknown',
          theme: retryTheme,
        });
      });
  };

  const hasActionHint = typeof apiError?.action === 'string';
  const shouldUseRetryAction = hasActionHint && apiError?.action === 'retry';
  const shouldUseAdjustAction = hasActionHint && apiError?.action === 'adjust';
  const isTimeAdjustCase = shouldUseAdjustAction && apiError?.actionTarget === 'time';
  const isConditionAdjustCase = shouldUseAdjustAction && apiError?.actionTarget === 'condition';
  const isCandidateAdjustCase = shouldUseAdjustAction && apiError?.actionTarget === 'candidate';
  const isApiAdjustCase = shouldUseAdjustAction && apiError?.actionTarget === 'api';
  const isMoodOrConditionAdjustCase = shouldUseAdjustAction && apiError?.actionTarget === 'mood_or_condition';
  const shouldUseSecondaryAction = typeof apiError?.secondaryAction === 'string';
  const isSecondaryTimeAdjustCase = shouldUseSecondaryAction && apiError?.secondaryAction === 'adjust' && apiError?.secondaryActionTarget === 'time';
  const isSecondaryConditionAdjustCase = shouldUseSecondaryAction && apiError?.secondaryAction === 'adjust' && apiError?.secondaryActionTarget === 'condition';
  const isSecondaryCandidateAdjustCase = shouldUseSecondaryAction && apiError?.secondaryAction === 'adjust' && apiError?.secondaryActionTarget === 'candidate';
  const isSecondaryApiAdjustCase = shouldUseSecondaryAction && apiError?.secondaryAction === 'adjust' && apiError?.secondaryActionTarget === 'api';
  const isSecondaryMoodOrConditionAdjustCase = shouldUseSecondaryAction && apiError?.secondaryAction === 'adjust' && apiError?.secondaryActionTarget === 'mood_or_condition';

  const handleErrorAction = () => {
    trackCourseEvent('retry_clicked', {
      action: apiError?.action || 'error_primary_action',
      failure_code: apiError?.errorClassLabel || apiError?.errorClass || 'unknown',
    });
    if (shouldUseRetryAction) return handleRetryCourse();
    if (isTimeAdjustCase) return onBack?.();
    if (isConditionAdjustCase) return onBack?.();
    if (isCandidateAdjustCase) return onBack?.();
    if (isApiAdjustCase) return handleRetryCourse();
    if (isMoodOrConditionAdjustCase) {
      return handleRetryCourse({
        theme: getSafeAlternateTheme(params),
        retry_action: 'retry_with_safe_alternate_theme',
      });
    }
    if (shouldUseAdjustAction) return onBack?.();
    return onBack?.();
  };
  const handleErrorActionSecondary = () => {
    trackCourseEvent('retry_clicked', {
      action: apiError?.secondaryAction || 'error_secondary_action',
      failure_code: apiError?.errorClassLabel || apiError?.errorClass || 'unknown',
    });
    if (isSecondaryTimeAdjustCase) return onBack?.();
    if (isSecondaryConditionAdjustCase) return onBack?.();
    if (isSecondaryCandidateAdjustCase) return onBack?.();
    if (isSecondaryApiAdjustCase) return handleRetryCourse();
    if (isSecondaryMoodOrConditionAdjustCase) return handleRetryCourse({
      theme: getSafeAlternateTheme(params),
      retry_action: 'retry_with_safe_alternate_theme',
    });
    if (shouldUseSecondaryAction && apiError.secondaryAction === 'retry') return handleRetryCourse();
    if (shouldUseSecondaryAction) return onBack?.();
    return null;
  };
  const errorButtonLabel = isTimeAdjustCase
    ? '시간대 변경 후 다시 보기'
    : isConditionAdjustCase
    ? '조건 변경하기'
    : isCandidateAdjustCase
    ? '조건 변경하기'
    : isMoodOrConditionAdjustCase
    ? '다른 분위기 추천'
    : isApiAdjustCase
    ? '다시 이어보기'
    : (apiError?.buttonLabel ?? '다시 이어보기');
  const secondaryErrorButtonLabel = isSecondaryTimeAdjustCase
    ? '시간대 변경하기'
    : isSecondaryConditionAdjustCase
    ? '조건 변경하기'
    : isSecondaryCandidateAdjustCase
    ? '조건 변경하기'
    : isSecondaryMoodOrConditionAdjustCase
    ? '다른 분위기 추천'
    : (apiError?.secondaryButtonLabel ?? null);

  const isEdit = mode === 'edit';
  const addBlockedReason = (() => {
    if (places.length < 5) return '장소가 5개 미만인 코스는 장소를 추가하지 않습니다.';
    if (regionStatus === 'LIMITED') return '데이터가 제한된 지역은 장소 추가를 지원하지 않습니다.';
    if (regionStatus === 'BLOCKED') return '현재 서비스 제한 지역은 장소 추가를 지원하지 않습니다.';
    return null;
  })();
  const canAddPlace = !hasAddedPlace && !addBlockedReason;

  const showToast = (message) => {
    setToastMessage(message);
    window.setTimeout(() => setToastMessage((current) => (current === message ? null : current)), 2400);
  };

  /* ── 아코디언 ── */
  const toggleAccordion = (id) => {
    setExpandedIds(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);
  };

  /* ── 드래그 ── */
  const handleDragStart = (e, index) => {
    if (!isEdit) return;
    setDraggingIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  };
  const handleDragEnter = (index) => {
    if (!isEdit || draggingIndex === null || draggingIndex === index) return;
    const next = [...places];
    const item = next.splice(draggingIndex, 1)[0];
    next.splice(index, 0, item);
    setDraggingIndex(index);
    setPlaces(next);
  };
  const handleDragEnd = () => {
    if (!isEdit) return;
    setDraggingIndex(null);
    setActiveDragId(null);
    setHasPendingRecalculate(true);
  };

  /* ── 후보 fetch (change/add 공통) ── */
  const fetchCandidates = (placeId, role, insertAfterPlaceId = null) => {
    if (!courseId) return;
    setCandidateLoading(true);
    setCandidates([]);
    const params = new URLSearchParams({ role });
    if (placeId) params.set('place_id', placeId);
    if (insertAfterPlaceId) params.set('insert_after_place_id', insertAfterPlaceId);
    const qs = params.toString();
    fetch(`/api/course/${courseId}/candidates?${qs}`)
      .then(res => { if (!res.ok) throw new Error(); return res.json(); })
      .then(data => {
        setCandidates((data.candidates || []).map(normalizeCandidate));
        setCandidateLoading(false);
      })
      .catch(() => { setCandidates([]); setCandidateLoading(false); });
  };

  /* ── 장소 변경 시트 ── */
  const openChangeSheet = (place, e) => {
    e.stopPropagation();
    setSelectedTargetPlace(place);
    setSheetMode('change');
    fetchCandidates(place.id, place.role);
  };

  /* ── 장소 추가 시트 ── */
  const openAddSheet = (index) => {
    if (addBlockedReason) {
      showToast(addBlockedReason);
      return;
    }
    const insertAfterPlaceId = places[index]?.place_id;
    if (!insertAfterPlaceId) return;
    setAddTargetIndex(index);
    setSheetMode('add');
    fetchCandidates(null, 'spot', String(insertAfterPlaceId));
  };

  /* ── 시트 닫기 ── */
  const closeSheet = () => {
    setSheetMode(null);
    setSelectedTargetPlace(null);
    setAddTargetIndex(null);
    setCandidates([]);
  };

  /* ── 장소 변경 확정 — PATCH /api/course/{id}/replace ── */
  const handleChangeConfirm = (candidateId) => {
    if (!courseId || candidateLoading) return;
    setCandidateLoading(true);
    fetch(`/api/course/${courseId}/replace`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_place_id: selectedTargetPlace.id,
        new_place_id:    candidateId,
      }),
    })
      .then(res => { if (!res.ok) throw new Error('선택한 장소가 잠깐 보이지 않았어요. 잠깐 뒤에 다시 눌러 주시면 돼요.'); return res.json(); })
      .then(data => {
        const normalized = (data.places || []).map(normalizePlace);
        setPlaces(normalized);
        setHasPendingRecalculate(true);
        setCandidateLoading(false);
        closeSheet();
      })
      .catch(() => { setCandidateLoading(false); closeSheet(); });
  };

  /* ── 장소 추가 확정 ── */
  // 장소 추가는 MVP 기준 spot role만 허용한다. meal/cafe 추가는 추후 확장 대상.
  const handleAddConfirm = (candidateId) => {
    const selected = candidates.find(c => c.id === candidateId);
    if (!selected) return;
    const newPlace = {
      id:           `added-${++_addPlaceCounter}`,
      place_id:     selected.place_id ?? null,
      time:         '재계산 필요',
      name:         selected.name,
      duration:     '1시간',
      duration_min: 60,
      role:         selected.category || 'spot',
      address:      selected.address,
      description:  '',
      image:        selected.image,
      lat:          selected.lat ?? null,
      lon:          selected.lon ?? null,
      transit:      '이동시간 계산 필요',
    };
    const next = [...places];
    next.splice(addTargetIndex + 1, 0, newPlace);
    setPlaces(next);
    setHasAddedPlace(true);
    setHasPendingRecalculate(true);
    closeSheet();
  };

  /* ── 저장하기 ── */
  const handleSave = () => {
    if (!courseId) {
      showToast('저장할 코스 정보가 없습니다.');
      return;
    }
    trackCourseEvent('save_clicked', {
      action: 'save_course',
      success: true,
    }, buildRouteMetrics(places));
    setSaving(true);
    const result = saveCourseToLocalStorage({
      course_id: courseId,
      region: params?.displayRegion || params?.region,
      summary: courseDesc,
      places,
      total_duration_min: totalDuration,
      total_travel_min: totalTravel,
      option_notice: optionNotice,
      missing_slot_reason: missingSlotReason,
      generation_params: params,
    });
    setSaving(false);
    if (!result.ok) {
      showToast('저장을 못했어요. 잠깐 뒤에 다시 눌러 주세요.');
      return;
    }
    showToast(result.action === 'updated' ? '이미 저장된 코스를 업데이트했어요.' : '코스를 저장했어요.');
    onSave?.();
  };

  const handleShare = async () => {
    trackCourseEvent('share_clicked', {
      action: 'share_course',
      success: true,
    }, buildRouteMetrics(places));
    const shareText = `${params?.displayRegion || params?.region || '여행'} 코스를 확인해 보세요.`;
    try {
      if (navigator.share) {
        await navigator.share({ title: '여행 코스', text: shareText, url: window.location.href });
        return;
      }
      await navigator.clipboard?.writeText(window.location.href);
      showToast('공유 링크를 복사했어요.');
    } catch {
      showToast('공유를 마무리하지 못했어요. 잠시 뒤 다시 눌러 주세요.');
    }
  };

  /* ── 경로 재계산 ── */
  const handleRecalculate = () => {
    if (!courseId) return;
    setLoading(true);
    const place_ids = places.map(p => p.id);
    const current_places = places.map(p => ({
      id:             p.id,
      place_id:       p.place_id ? String(p.place_id) : null,
      name:           p.name,
      visit_role:     p.role,
      latitude:       p.lat ?? null,
      longitude:      p.lon ?? null,
      duration_min:   p.duration_min ?? null,
      first_image_url: p.image ?? null,
    }));
    fetch(`/api/course/${courseId}/recalculate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ place_ids, current_places, departure_time: params?.departure_time }),
    })
      .then(async res => {
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || '코스 정리가 잠깐 멈췄어요. 잠시 뒤에 다시 눌러 주세요.');
        }
        return res.json();
      })
      .then(data => {
        setPlaces((data.places || []).map(normalizePlace));
        setTotalDuration(data.total_duration_min ?? null);
        setTotalTravel(data.total_travel_min ?? null);
        setHasPendingRecalculate(false);
        setMode('view');
        setLoading(false);
      })
      .catch(err => {
        console.error('[Recalculate]', err);
        showToast(err.message || '코스 정리를 바로 마무리하지 못했어요. 잠시 뒤에 다시 눌러 주세요.');
        setLoading(false);
      });
  };

  /* ── 완료 ── */
  const handleComplete = () => {
    if (hasPendingRecalculate) return;
    setMode('view');
  };

  /* ── 현재 시트 데이터 ── */
  const sheetData = (() => {
    if (sheetMode === 'change' && selectedTargetPlace) {
      const role = selectedTargetPlace.role;
      return {
        title:    SHEET_TITLE[role] || '장소 교체',
        description: `현재 코스 흐름을 유지하면서\n선택할 수 있는 장소를 추천드려요.`,
        badgeLabel: '변경 대상',
        badgeText:  selectedTargetPlace.name,
        btnText:   '변경',
        btnIcon:   <CheckIcon size={12} color="#2563EB" />,
        infoText:  '선택한 장소로 일정이 바로 업데이트됩니다.',
        onSelect:  handleChangeConfirm,
      };
    }
    if (sheetMode === 'add') {
      const prevName = places[addTargetIndex]?.name || '';
      const nextName = places[addTargetIndex + 1]?.name || '다음 장소';
      return {
        title:    '장소 추가',
        description: '슬롯 사이에 추가할 수 있는\n장소를 추천드려요. (1회 가능)',
        badgeLabel: '추가 위치',
        badgeText: `${prevName} → ${nextName} 사이`,
        btnText:   '추가',
        btnIcon:   <PlusIcon size={12} color="#2563EB" />,
        infoText:  '장소는 최대 1곳만 추가할 수 있어요.',
        onSelect:  handleAddConfirm,
      };
    }
    return null;
  })();

  /* ── 렌더 ── */
  /* ── 로딩 화면 ── */
  if (loading) {
    return (
      <div className="bg-[#F8FAFC] min-h-[100dvh] flex flex-col">
        <ResultMotionStyles />
        <div className="flex items-center justify-between px-4 py-4">
          <button onClick={onBack} className="min-w-[44px] min-h-[44px] flex items-center justify-center -ml-2 rounded-full active:bg-gray-50" aria-label="뒤로가기"><BackIcon /></button>
          <h2 className="text-[17px] font-bold text-[#111827]">추천 코스</h2>
          <div className="w-8" />
        </div>
        <div className="flex-1 px-5 pt-8 pb-24">
          <div className="mb-7 text-center">
            <div className="mx-auto mb-3 h-10 w-10 rounded-full border-4 border-[#BFDBFE] border-t-[#2563EB] animate-spin" />
            <p className="text-[15px] font-extrabold text-[#111827]">새 코스 흐름을 맞추는 중이에요</p>
            <p className="mt-1 text-[12px] font-semibold text-[#64748B]">장소와 이동 순서를 정리하고 있어요.</p>
          </div>
          <div className="space-y-3">
            {[0, 1, 2].map((item) => (
              <div key={item} className="relative overflow-hidden rounded-[20px] border border-[#EEF2F7] bg-white p-3 shadow-[0_4px_16px_rgba(15,23,42,0.05)] course-soft-in" style={{ animationDelay: `${item * 70}ms` }}>
                <div className="route-skeleton-shimmer absolute inset-0 overflow-hidden" aria-hidden="true" />
                <div className="relative flex items-center gap-3">
                  <div className="h-[58px] w-[58px] rounded-[16px] bg-[#E2E8F0]" />
                  <div className="flex-1 space-y-2">
                    <div className="h-3 w-2/3 rounded-full bg-[#E2E8F0]" />
                    <div className="h-3 w-1/2 rounded-full bg-[#EEF2F7]" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  /* ── 에러 화면 ── */
  if (apiError) {
    return (
      <div className="bg-[#F8FAFC] min-h-[100dvh] flex flex-col">
        <div className="flex items-center justify-between px-4 py-4">
          <button onClick={onBack} className="min-w-[44px] min-h-[44px] flex items-center justify-center -ml-2 rounded-full active:bg-gray-50" aria-label="뒤로가기"><BackIcon /></button>
          <h2 className="text-[17px] font-bold text-[#111827]">추천 코스</h2>
          <div className="w-8" />
        </div>
        <div className="flex-1 flex flex-col items-center justify-center gap-4 px-6 pb-40">
          <div className="w-12 h-12 bg-[#FEF2F2] rounded-full flex items-center justify-center">
            <WarnIcon />
          </div>
          <p className="text-[16px] font-bold text-[#111827] text-center">{apiError.title}</p>
          <p className="text-[13px] text-[#64748B] text-center">{apiError.message}</p>
          {apiError.hints?.length > 0 && (
            <ul className="text-[13px] text-[#64748B] text-left list-disc pl-5 leading-relaxed">
              {apiError.hints.map((hint) => (
                <li key={hint}>{hint}</li>
              ))}
            </ul>
          )}
          <button
            onClick={handleErrorAction}
            className="mt-2 px-6 py-3 bg-[#2563EB] text-white text-[14px] font-bold rounded-full"
          >
            {errorButtonLabel}
          </button>
          {secondaryErrorButtonLabel && (
            <button
              onClick={handleErrorActionSecondary}
              className="mt-2 px-6 py-3 border border-[#BFDBFE] text-[#1D4ED8] text-[14px] font-bold rounded-full bg-white"
            >
              {secondaryErrorButtonLabel}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-[#F8FAFC] min-h-[100dvh] flex flex-col relative overflow-x-hidden">
      <ResultMotionStyles />
      {toastMessage && (
        <div
          className="fixed left-5 right-5 z-[120] rounded-2xl bg-[#111827] px-4 py-3 text-center text-[13px] font-bold text-white shadow-[0_12px_30px_rgba(15,23,42,0.22)]"
          style={{ bottom: 'calc(168px + env(safe-area-inset-bottom, 0px))' }}
          role="status"
        >
          {toastMessage}
        </div>
      )}

      {/* 헤더 */}
      <div className="bg-[#F8FAFC] sticky top-0 z-20">
        <div className="flex items-center justify-between px-4 py-4">
          <button onClick={onBack} className="min-w-[44px] min-h-[44px] flex items-center justify-center -ml-2 rounded-full active:bg-gray-50" aria-label="뒤로가기"><BackIcon /></button>
          <h2 className="text-[17px] font-bold text-[#111827]">추천 코스</h2>
          <button onClick={handleShare} className="min-w-[44px] min-h-[44px] flex items-center justify-center -mr-2 rounded-full active:bg-gray-50" aria-label="공유하기"><ShareIcon /></button>
        </div>
        {courseDesc && (
          <p className="text-[12px] text-[#64748B] text-center px-5 pb-3 -mt-2">{courseDesc}</p>
        )}
        {missingSlotReason && (
          <div className="flex items-center justify-center gap-1.5 px-5 pb-3 -mt-1">
            <InfoIcon />
            <p className="text-[11px] text-[#60A5FA] leading-snug">{missingSlotReason}</p>
          </div>
        )}
        {optionNotice && (
          <div className="flex items-center justify-center gap-1.5 px-5 pb-3 -mt-1">
            <InfoIcon />
            <p className="text-[11px] text-[#60A5FA] leading-snug">{optionNotice}</p>
          </div>
        )}
      </div>

      <div className="px-5 pt-2" style={{ paddingBottom: resultListBottomPadding }}>
        {/* 상단 태그 */}
        <div className="flex items-center gap-2 mb-6">
          <div className="px-3 py-1.5 bg-white border border-[#3B82F6] text-[#3B82F6] text-[12px] font-bold rounded-full shadow-sm flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-[#3B82F6]"></span> {params?.region ?? ''} 코스
          </div>
          <div className="px-3 py-1.5 bg-white border border-[#E2E8F0] text-[#475569] text-[12px] font-bold rounded-full shadow-sm flex items-center gap-1">
            <span className="text-[#3B82F6]">🕐</span> {params?.departure_time ?? ''}
          </div>
        </div>

        {/* 타임라인 */}
        <div className="flex flex-col course-soft-in">
          {places.length === 0 ? (
            <div className="py-10 px-4 text-center text-[13px] text-[#64748B]">
              <p className="mb-2 font-semibold text-[#334155]">지금은 추천이 잠깐 적게 보여요</p>
              <p>조건을 한 번 바꿔서 다시 만들어보면 바로 이어드릴게요.</p>
            </div>
          ) : (
            places.map((place, index) => {
            const isExpanded = expandedIds.includes(place.id);
            const isDragging = draggingIndex === index;
            const isDraggable = isEdit && activeDragId === place.id;
            const hasNext = index < places.length - 1;
            const roleLabel = ROLE_LABEL[place.role] || '추천 장소';
            const displayDescription = getDisplayPlaceDescription(place, {
              region: params?.displayRegion || params?.region,
              index,
            });

            return (
              <div
                key={place.id}
                draggable={isDraggable}
                onDragStart={(e) => handleDragStart(e, index)}
                onDragEnter={() => handleDragEnter(index)}
                onDragEnd={handleDragEnd}
                onDragOver={(e) => e.preventDefault()}
                className={`relative transition-all duration-200 ${isDragging ? 'opacity-40' : 'opacity-100'}`}
              >
                {/* 시간 */}
                <div className="flex items-center gap-1.5 mb-1.5 pl-0.5">
                  <span className="text-[13px] font-extrabold text-[#111827] w-[45px] leading-none">{place.time}</span>
                  {place.endTime && (
                    <span className="text-[11px] font-semibold text-[#9CA3AF] leading-none">~ {place.endTime}</span>
                  )}
                </div>

                {/* 카드 + 타임라인 축 */}
                <div className="flex items-stretch relative">
                  <div className="w-[45px] shrink-0 flex flex-col items-center relative z-0">
                    <div className="w-[22px] h-[22px] rounded-full bg-[#2563EB] text-white z-10 mt-[22px] flex items-center justify-center text-[11px] font-extrabold shadow-[0_3px_8px_rgba(37,99,235,0.24)]">
                      {index + 1}
                    </div>
                    {hasNext && <div className="absolute top-[42px] bottom-0 w-[2px] bg-[#BFDBFE]" />}
                  </div>

                  <div className="flex-1 pb-3 relative z-10">
                    <div className="bg-white rounded-[20px] border border-[#F1F5F9] shadow-[0_4px_16px_rgba(15,23,42,0.055)] overflow-visible">

                      {/* 카드 헤더 */}
                      <div className="flex items-center gap-3.5 px-3 py-3.5">
                        {place.image ? (
                          <img
                            src={place.image}
                            className={`w-[60px] h-[60px] object-cover rounded-[14px] transition-all duration-300 ${isExpanded ? 'opacity-0 w-0 h-0 ml-[-12px]' : 'opacity-100'}`}
                            alt={place.name}
                          />
                        ) : (
                          <PlaceholderVisual
                            place={place}
                            params={params}
                            size="sm"
                            className={`transition-all duration-300 ${isExpanded ? 'opacity-0 w-0 h-0 ml-[-12px]' : 'opacity-100'}`}
                          />
                        )}
                        <div className="flex-1 min-w-0 cursor-pointer py-0.5" onClick={() => toggleAccordion(place.id)}>
                          <h4 className="text-[16px] leading-snug font-extrabold text-[#1F2937] truncate mb-1">{place.name}</h4>
                          <p className="text-[12px] leading-snug text-[#64748B] font-semibold truncate">
                            {roleLabel} · {place.duration}
                          </p>

                          {/* edit 모드: role 기반 변경 버튼 */}
                          {isEdit && (
                            <button
                              onClick={(e) => openChangeSheet(place, e)}
                              className="mt-2.5 px-3 py-1.5 bg-[#F1F5F9] text-[#475569] text-[12px] font-bold rounded-lg active:bg-gray-200 transition-colors"
                            >
                              {CHANGE_LABEL[place.role] || '장소 변경'}
                            </button>
                          )}
                        </div>

                        <div className="flex flex-col items-center gap-1 px-1">
                          <button onClick={() => toggleAccordion(place.id)} className="p-1 text-[#9CA3AF]">
                            <ChevronIcon isOpen={isExpanded} />
                          </button>
                          {/* edit 모드: 드래그 핸들 */}
                          {isEdit && (
                            <div
                              onMouseDown={() => setActiveDragId(place.id)}
                              onMouseUp={() => setActiveDragId(null)}
                              className="p-1 cursor-grab active:cursor-grabbing text-[#CBD5E1]"
                            >
                              <DragHandleIcon />
                            </div>
                          )}
                        </div>
                      </div>

                      {/* 아코디언 펼침 */}
                      {isExpanded && (
                        <div className="px-4 pb-4 pt-1 border-t border-[#F1F5F9]/70">
                          {place.image ? (
                            <img src={place.image} className="w-full max-h-[240px] object-cover rounded-[16px] mb-3.5 mt-3 shadow-sm" alt={place.name} />
                          ) : (
                            <PlaceholderVisual place={place} params={params} size="lg" className="mb-3.5 mt-3" />
                          )}
                          <p
                            className="text-[13px] text-[#475569] leading-[1.62] mb-1 whitespace-pre-line break-words"
                            style={{
                              maxHeight: '105px',
                              overflow: 'hidden',
                            }}
                          >
                            {displayDescription}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* 이동시간 + 장소 추가 버튼 */}
                {hasNext && (
                  <div className="flex items-stretch min-h-[44px] pb-3">
                    <div className="w-[45px] shrink-0 flex flex-col items-center justify-center relative z-0">
                      <div className="absolute top-0 bottom-0 w-[2px] bg-[#3B82F6]" />
                      <div className="w-[5px] h-[5px] rounded-full bg-[#3B82F6] z-10" />
                    </div>
                    <div className="flex-1 flex justify-start items-center relative z-10 pl-2">
                      <div className="px-3.5 py-2 bg-white border border-[#E2E8F0] rounded-full shadow-[0_2px_8px_rgba(0,0,0,0.04)] flex items-center gap-1.5">
                        <CarIcon />
                        <span className="text-[11px] font-bold text-[#475569]">{place.transit}</span>
                      </div>

                      {/* edit 모드 + 안전 조건을 통과한 경우에만 + 버튼 노출 */}
                      {isEdit && canAddPlace && (
                        <button
                          onClick={() => openAddSheet(index)}
                          className="absolute right-4 w-[34px] h-[34px] bg-white border border-[#E2E8F0] rounded-full flex items-center justify-center shadow-sm active:bg-gray-50 transition-colors"
                        >
                          <PlusIcon size={16} />
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          }))}
        </div>

        {/* 총 소요 시간 요약 */}
        {(totalDuration != null || totalTravel != null) && (
          <div className="mt-6 p-4 bg-white border border-[#F1F5F9] rounded-[20px] shadow-sm flex items-center justify-center gap-5">
            {totalDuration != null && (
              <div className="flex items-center gap-2">
                <ClockIcon />
                <span className="text-[14px] font-extrabold text-[#111827]">
                  총 {Math.floor(totalDuration / 60)}시간{totalDuration % 60 ? ` ${totalDuration % 60}분` : ''}
                </span>
              </div>
            )}
            {totalDuration != null && totalTravel != null && (
              <div className="w-[1px] h-[14px] bg-[#E2E8F0]" />
            )}
            {totalTravel != null && (
              <div className="flex items-center gap-2">
                <MapPinIcon />
                <span className="text-[14px] font-bold text-[#475569]">이동 {totalTravel}분</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 하단 고정 버튼 */}
      <div
        className="fixed left-0 right-0 px-6 pt-16 bg-gradient-to-t from-[#F8FAFC] via-[#F8FAFC]/95 to-transparent z-30 flex flex-col gap-2.5 pointer-events-none"
        style={{ bottom: bottomNavOffset, paddingBottom: '16px' }}
      >
        {mode === 'view' ? (
          <>
            <button
              onClick={handleRemakeMoodClick}
              disabled={regeneratePending}
              aria-busy={regeneratePending}
              className="w-full h-[52px] bg-white text-[#3B82F6] font-bold text-[14px] border border-[#E2E8F0] rounded-full shadow-sm active:bg-gray-50 disabled:opacity-80 pointer-events-auto flex items-center justify-center gap-2 transition-all duration-150"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              {regeneratePending ? '새 흐름 준비 중' : '다른 분위기 추천'}
            </button>
            <div className="flex gap-2.5 pointer-events-auto">
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex-1 h-[52px] bg-white text-[#2563EB] font-bold text-[14px] border border-[#BFDBFE] rounded-full shadow-sm active:bg-blue-50 disabled:opacity-60"
              >
                {saving ? '저장 중' : '이 코스 저장하기'}
              </button>
              <button onClick={() => setMode('edit')} className="flex-1 h-[52px] bg-[#2563EB] text-white font-bold text-[15px] rounded-full shadow-[0_8px_20px_rgba(37,99,235,0.35)] active:scale-[0.98]">일정 편집</button>
            </div>
          </>
        ) : (
          <>
            {addBlockedReason && (
              <div className="pointer-events-auto flex items-center gap-2 px-4 py-3 bg-[#EFF6FF] border border-[#BFDBFE] rounded-2xl mb-1">
                <InfoIcon />
                <span className="text-[13px] font-semibold text-[#2563EB]">{addBlockedReason}</span>
              </div>
            )}
            {/* 재계산 필요 시 항상 안내 노출 */}
            {hasPendingRecalculate && (
              <div className="pointer-events-auto flex items-center gap-2 px-4 py-3 bg-[#FFFBEB] border border-[#FCD34D] rounded-2xl mb-1">
                <WarnIcon />
                <span className="text-[13px] font-semibold text-[#92400E]">경로가 바뀌어 다시 맞춰야 해요.</span>
              </div>
            )}
            {manualEditTravelWarning && (
              <div className="pointer-events-auto flex items-center gap-2 px-4 py-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-2xl mb-1">
                <InfoIcon />
                <span className="text-[13px] font-semibold text-[#475569]">이동시간이 조금 길어요. 일정 편집에서 조정할 수 있어요.</span>
              </div>
            )}

            <button
              onClick={handleRecalculate}
              className={`w-full h-[52px] font-bold text-[15px] border rounded-full shadow-sm pointer-events-auto transition-colors ${
                hasPendingRecalculate
                  ? 'bg-white text-[#2563EB] border-[#2563EB] active:bg-blue-50'
                  : 'bg-white text-[#94A3B8] border-[#E2E8F0]'
              }`}
            >
              경로 다시 맞추기
            </button>
            <button
              onClick={handleComplete}
              disabled={hasPendingRecalculate}
              className={`w-full h-[56px] font-bold text-[16px] rounded-full pointer-events-auto transition-all ${
                hasPendingRecalculate
                  ? 'bg-[#CBD5E1] text-white cursor-not-allowed'
                  : 'bg-[#2563EB] text-white shadow-[0_8px_20px_rgba(37,99,235,0.35)] active:scale-[0.98]'
              }`}
            >
              추천 완료
            </button>
          </>
        )}
      </div>

      {/* 바텀시트 */}
      {sheetMode && sheetData && (
        <>
          <div className="fixed inset-0 bg-black/40 z-[100]" onClick={closeSheet} />
          <div className="fixed bottom-0 left-0 right-0 bg-white rounded-t-[32px] z-[101] flex flex-col h-[85vh] animate-slide-up">
            <div className="flex-1 overflow-y-auto pb-8">

              {/* 시트 헤더 */}
              <div className="sticky top-0 bg-white z-10 px-6 pt-6 pb-2 rounded-t-[32px]">
                <div className="flex items-center justify-between mb-4">
                  <button onClick={closeSheet} className="min-w-[44px] min-h-[44px] flex items-center justify-center -ml-2 rounded-full active:bg-gray-50" aria-label="닫기"><BackIcon /></button>
                  <h3 className="text-[18px] font-bold text-[#111827]">{sheetData.title}</h3>
                  <button onClick={closeSheet} className="min-w-[44px] min-h-[44px] flex items-center justify-center -mr-2 rounded-full active:bg-gray-50" aria-label="닫기"><CloseIcon /></button>
                </div>
                <p className="text-[15px] text-[#475569] font-medium leading-relaxed mb-4 whitespace-pre-line">
                  {sheetData.description}
                </p>
                <div className="inline-block px-4 py-2 bg-[#F8FAFC] rounded-xl text-[#64748B] text-[13px] font-semibold mb-2">
                  {sheetData.badgeLabel}: <span className="text-[#3B82F6]">{sheetData.badgeText}</span>
                </div>
              </div>

              {/* 후보 리스트 */}
              <div className="px-6 space-y-4 mt-2">
                {candidateLoading ? (
                  /* 스켈레톤 */
                  [1, 2, 3].map((n) => (
                    <div key={n} className="flex items-center gap-4 p-4 rounded-[20px] border border-[#F1F5F9] bg-white shadow-sm animate-pulse">
                      <div className="w-[72px] h-[72px] bg-[#F1F5F9] rounded-2xl" />
                      <div className="flex-1 space-y-2">
                        <div className="h-4 bg-[#F1F5F9] rounded w-3/4" />
                        <div className="h-3 bg-[#F1F5F9] rounded w-1/2" />
                        <div className="h-3 bg-[#F1F5F9] rounded w-2/3" />
                      </div>
                      <div className="w-[60px] h-[34px] bg-[#F1F5F9] rounded-xl" />
                    </div>
                  ))
                ) : candidates.length === 0 ? (
                  <p className="text-center text-[13px] text-[#94A3B8] py-8">
                    아직 표시할 추천 후보가 없어요. 테마·지역을 바꿔 다시 찾아보세요.
                  </p>
                ) : (
                  candidates.map((c) => (
                    <div key={c.id} className="flex items-center gap-4 p-4 rounded-[20px] border border-[#F1F5F9] bg-white shadow-sm">
                      {c.image
                        ? <img src={c.image} className="w-[72px] h-[72px] object-cover rounded-2xl" alt={c.name} />
                        : <PlaceholderVisual place={c} params={params} size="md" />
                      }
                      <div className="flex-1 py-1">
                        <h4 className="text-[15px] font-bold text-[#111827] mb-1">{c.name}</h4>
                        {c.rating != null && (
                          <div className="flex items-center gap-1.5 mb-1.5">
                            <StarIcon />
                            <span className="text-[13px] font-bold text-[#475569]">
                              {c.rating}
                              {c.reviews != null && <span className="text-[#94A3B8] font-normal"> ({c.reviews.toLocaleString()})</span>}
                            </span>
                          </div>
                        )}
                        <p className="text-[12px] text-[#64748B]">{ROLE_LABEL[c.category] || c.category}{c.transit ? ` · ${c.transit}` : ''}</p>
                      </div>
                      <button
                        disabled={candidateLoading}
                        onClick={() => sheetData.onSelect(c.id)}
                        className="px-3.5 py-2 border border-[#E2E8F0] rounded-xl text-[13px] font-bold text-[#2563EB] active:bg-gray-50 flex items-center gap-1 disabled:opacity-40"
                      >
                        {sheetData.btnIcon} {sheetData.btnText}
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* 시트 하단 안내 */}
            <div className="px-6 pb-8 pt-4 bg-white border-t border-[#F1F5F9] shrink-0">
              <div className="p-4 bg-[#EFF6FF] rounded-2xl flex items-center gap-2">
                <InfoIcon />
                <span className="text-[14px] text-[#3B82F6] font-medium">{sheetData.infoText}</span>
              </div>
            </div>
          </div>
        </>
      )}

      <style>{`
        @keyframes slide-up { from { transform: translateY(100%); } to { transform: translateY(0); } }
        .animate-slide-up { animation: slide-up 0.3s ease-out forwards; }
      `}</style>
    </div>
  );
}


