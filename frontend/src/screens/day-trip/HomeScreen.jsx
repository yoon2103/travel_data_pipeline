import { useState, useEffect, useRef } from 'react';
import BottomSheet from '../../components/common/BottomSheet';
import {
  REGIONS, REGION_TO_DB, HERO_FALLBACK_IMAGE, HERO_SLIDES, STATIC_ANCHORS, THEME_SEED_TO_MOOD,
  SEOUL_CURATED_ANCHOR_ZONE_IDS,
} from '../../data/dayTripDummyData';
import { trackEvent } from '../../utils/telemetry';

const AUTO_DEPARTURE_TIME = '내일 09:00';
const TIME_BAND_OPTIONS = [
  {
    id: 'morning',
    label: '아침',
    time: '09:00',
  },
  {
    id: 'daytime',
    label: '낮',
    time: '12:00',
  },
  {
    id: 'evening',
    label: '저녁',
    time: '17:00',
  },
];

const DEFAULT_TIME_BAND = 'daytime';
const getTimeBandOption = (id) => TIME_BAND_OPTIONS.find((item) => item.id === id) || TIME_BAND_OPTIONS[1];
const mapTimeBandToDepartureTime = (bandId, dateLabel = '오늘') => `${dateLabel} ${getTimeBandOption(bandId).time}`;
const inferTimeBandFromDepartureTime = (value) => {
  const match = String(value || '').match(/(\d{1,2}):(\d{2})/);
  if (!match) return DEFAULT_TIME_BAND;
  const hour = Number(match[1]);
  if (hour < 11) return 'morning';
  if (hour < 16) return 'daytime';
  return 'evening';
};
const isEveningTimeBand = (bandId) => bandId === 'evening';

/* ─── 1. 전역 스타일 (스크롤바 제거 + 하단 탭바 강제 숨김) ────────── */
const GlobalStyles = () => (
  <style>{`
/* 기존 스크롤바 제거 속성 */
.hide-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
.hide-scrollbar::-webkit-scrollbar {
  display: none !important;
  width: 0 !important;
  height: 0 !important;
}
*::-webkit-scrollbar {
  display: none !important;
}
* {
  -ms-overflow-style: none !important;
  scrollbar-width: none !important;
}

/* 🔥 바텀시트 열릴 때 하단 탭바 강제 숨김 (body 클래스 연동) */
body.sheet-is-open nav,
body.sheet-is-open footer,
body.sheet-is-open [class*="tab-bar"],
body.sheet-is-open [class*="TabBar"],
body.sheet-is-open [class*="bottom-nav"],
body.sheet-is-open [id*="tab"],
body.sheet-is-open [id*="bottom"] {
  display: none !important;
  opacity: 0 !important;
  pointer-events: none !important;
  z-index: -100 !important;
}
  `}</style>
);

/* ─── 2. SVG 아이콘들 ────────────────────────────────── */
const PinIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" fill="#DBEAFE" stroke="#2563EB" strokeWidth="1.6" />
    <circle cx="12" cy="9" r="2.5" fill="#2563EB" />
  </svg>
);

const ClockIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <circle cx="12" cy="12" r="9" fill="#DBEAFE" stroke="#2563EB" strokeWidth="1.6" />
    <path d="M12 7v5l3.5 3.5" stroke="#2563EB" strokeWidth="1.7" strokeLinecap="round" />
  </svg>
);

const GreyFlagIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" stroke="#94A3B8" strokeWidth="1.6" strokeLinejoin="round" />
    <line x1="4" y1="22" x2="4" y2="15" stroke="#94A3B8" strokeWidth="1.6" strokeLinecap="round" />
  </svg>
);

const BlueSearchIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <circle cx="11" cy="11" r="8" stroke="#2563EB" strokeWidth="2.2" />
    <line x1="21" y1="21" x2="16.65" y2="16.65" stroke="#2563EB" strokeWidth="2.2" strokeLinecap="round" />
  </svg>
);

const Chevron = ({ color = '#CBD5E1', size = 14 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <path d="M9 18l6-6-6-6" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const mergeDepartureOptions = (dbRegion, apiDepartures = []) => {
  const curated = STATIC_ANCHORS[dbRegion] || [];
  const broadCurated = curated.filter((item) => !isSeoulCuratedAnchor(item));
  const vibeCurated = curated.filter((item) => isSeoulCuratedAnchor(item));
  const merged = [];
  const seen = new Set();
  const ordered = dbRegion === '서울'
    ? [...vibeCurated, ...broadCurated, ...apiDepartures]
    : [...broadCurated, ...apiDepartures, ...vibeCurated];
  ordered.forEach((item) => {
    if (!item) return;
    const key = item.zone_id || item.name;
    if (!key || seen.has(key)) return;
    seen.add(key);
    merged.push(item);
  });
  return merged;
};

const isSeoulCuratedAnchor = (item) => (
  !!item?.is_curated_vibe || SEOUL_CURATED_ANCHOR_ZONE_IDS.includes(item?.zone_id)
);

const moodFromAnchorSeed = (item) => (
  item?.theme_seed ? THEME_SEED_TO_MOOD[item.theme_seed] : null
);

const isNightFriendlyAnchor = (item, bandId) => (
  isEveningTimeBand(bandId) && !item?.suppress_night_friendly
);


/* ─── 4. 입력 카드 컴포넌트 ────────────────────────── */
function InputCard({ icon, value, placeholder, onTap }) {
  const isPlaceholder = !value || value === placeholder;
  return (
    <button
      onClick={onTap}
      style={{
        width: '100%', height: 64, display: 'flex', alignItems: 'center', gap: 14, padding: '0 16px',
        background: '#FFFFFF', borderRadius: 16, border: '1px solid #F1F5F9', boxShadow: '0 2px 12px rgba(0,0,0,0.06)', cursor: 'pointer', textAlign: 'left'
      }}
    >
      <div style={{
        width: 36, height: 36, borderRadius: 10, background: '#EFF6FF',
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
      }}>{icon}</div>
      <span style={{ flex: 1, fontSize: isPlaceholder ? 14 : 16, fontWeight: isPlaceholder ? 500 : 800, color: isPlaceholder ? '#94A3B8' : '#111827' }}>
        {value || placeholder}
      </span>
      <span style={{ fontSize: 14, fontWeight: 700, color: '#2563EB', flexShrink: 0 }}>변경</span>
    </button>
  );
}

/* ─── 4. 홈 스크린 메인 ────────────────────────────── */
export default function HomeScreen({ onNext, courseParams, onParamChange }) {
  const [region, setRegion] = useState(courseParams?.displayRegion || '서울');
  const [regionList, setRegionList] = useState(REGIONS);
  const [selectedAnchor, setSelectedAnchor] = useState(courseParams?._homeAnchor || null);
  const [departures, setDepartures] = useState([]);
  const [departuresLoading, setDeparturesLoading] = useState(false);
  const [regionSheet, setRegionSheet] = useState(false);
  const [deptSheet, setDeptSheet] = useState(false);
  const [heroSlideIndex, setHeroSlideIndex] = useState(0);

  // departure_time 문자열 "오늘 9:00" 파싱 → 시트 선택기 초기값 복원
  const _parsedTime = (() => {
    const m = courseParams?.departure_time?.match(/^(오늘|내일)\s+(\d+):(\d{2})/);
    return m ? { date: m[1], hour: m[2], minute: m[3] } : null;
  })();
  const initialTimeBand = courseParams?.selected_time_band || inferTimeBandFromDepartureTime(courseParams?.departure_time);
  const [selectedTimeBand, setSelectedTimeBand] = useState(initialTimeBand);
  const [timeBandExpanded, setTimeBandExpanded] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const generatingResetTimerRef = useRef(null);
  const [departureTime, setDepartureTime] = useState(
    courseParams?.mapped_departure_time || courseParams?.departure_time || mapTimeBandToDepartureTime(initialTimeBand)
  );
  const [departureTimeUserSelected, setDepartureTimeUserSelected] = useState(true);
  const [timeSheet, setTimeSheet] = useState(false);
  const [selectedDate, setSelectedDate] = useState(_parsedTime?.date || '오늘');
  const [selectedHour, setSelectedHour] = useState(_parsedTime?.hour || null);
  const [selectedMinute, setSelectedMinute] = useState(_parsedTime?.minute || '00');

  const dbRegion = REGION_TO_DB[region] ?? region;

  useEffect(() => {
    fetch('/api/regions')
      .then(r => r.json())
      .then(data => { if (data.regions?.length) setRegionList(data.regions); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (regionSheet || deptSheet || timeSheet) {
      document.body.classList.add('sheet-is-open');
    } else {
      document.body.classList.remove('sheet-is-open');
    }
    return () => { document.body.classList.remove('sheet-is-open'); };
  }, [regionSheet, deptSheet, timeSheet]);

  useEffect(() => {
    if (HERO_SLIDES.length <= 1) return undefined;
    const timer = window.setInterval(() => {
      setHeroSlideIndex((current) => (current + 1) % HERO_SLIDES.length);
    }, 4200);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => () => {
    if (generatingResetTimerRef.current) {
      window.clearTimeout(generatingResetTimerRef.current);
    }
  }, []);

  function handleTimeConfirm() {
    if (!selectedHour) return;
    const time = `${selectedDate} ${selectedHour}:${selectedMinute}`;
    setDepartureTime(time);
    setDepartureTimeUserSelected(true);
    onParamChange('departure_time', time);
    onParamChange('departure_time_user_selected', true);
    setTimeSheet(false);
  }

  function handleTimeBandSelect(bandId) {
    const mappedTime = mapTimeBandToDepartureTime(bandId);
    setSelectedTimeBand(bandId);
    setTimeBandExpanded(false);
    setDepartureTime(mappedTime);
    setDepartureTimeUserSelected(true);
    onParamChange('selected_time_band', bandId);
    onParamChange('mapped_departure_time', mappedTime);
    onParamChange('departure_time', mappedTime);
    onParamChange('departure_time_user_selected', true);
    onParamChange('time_band_night_friendly', isNightFriendlyAnchor(selectedAnchor, bandId));
  }

  function handleRegionSelect(r) {
    const db = REGION_TO_DB[r] ?? r;
    trackEvent('region_selected', {
      region: db,
      display_region: r,
      screen: 'home',
    });
    setRegion(r);
    setSelectedAnchor(null);
    setDepartures([]);
    setRegionSheet(false);
    onParamChange('displayRegion', r);
    onParamChange('region', db);
    onParamChange('start_anchor', null);
    onParamChange('start_anchor_label', null);
    onParamChange('start_lat', null);
    onParamChange('start_lon', null);
    onParamChange('zone_id', null);
    onParamChange('selected_anchor_vibe', null);
    onParamChange('anchor_theme_seed', null);
    onParamChange('anchor_district', null);
    onParamChange('is_curated_vibe_anchor', false);
    onParamChange('condition_options_collapsed', false);
    onParamChange('mood_seeded_by_anchor', false);
    onParamChange('default_preset_mode', true);
    onParamChange('_homeAnchor', null);
  }

  function openDeptSheet() {
    setDeptSheet(true);
    setDeparturesLoading(true);
    setDepartures([]);
    fetch(`/api/region/${dbRegion}/departures`)
      .then(r => {
        if (!r.ok || !r.headers.get('content-type')?.includes('application/json')) {
          throw new Error('non_json');
        }
        return r.json();
      })
      .then(data => {
        const list = data.departures || [];
        if (list.length > 0) {
          setDepartures(mergeDepartureOptions(dbRegion, list));
        } else {
          setDepartures(STATIC_ANCHORS[dbRegion] || []);
        }
        setDeparturesLoading(false);
      })
      .catch(() => {
        setDepartures(STATIC_ANCHORS[dbRegion] || []);
        setDeparturesLoading(false);
      });
  }

  // 출발 기준점 선택이 필수: 모든 지역에서 anchor 좌표 기반으로 코스 생성
  const canGenerate = !!departureTime && !!selectedAnchor;

  function handleNext() {
    if (!canGenerate || isGenerating) return;
    setIsGenerating(true);
    if (generatingResetTimerRef.current) {
      window.clearTimeout(generatingResetTimerRef.current);
    }
    generatingResetTimerRef.current = window.setTimeout(() => {
      setIsGenerating(false);
      generatingResetTimerRef.current = null;
    }, 3500);
    trackEvent('course_generate_start', {
      region: dbRegion,
      display_region: region,
      selected_anchor: selectedAnchor.selected_anchor ?? selectedAnchor.name,
      departure_anchor: selectedAnchor.name,
      anchor_district: selectedAnchor.district ?? null,
      vibe: selectedAnchor.selected_anchor ?? selectedAnchor.name,
      mood: courseParams?.mood,
      theme: selectedAnchor.theme_seed ?? null,
      selected_time_band: selectedTimeBand,
      mapped_departure_time: departureTime,
      screen: 'home',
    });
    onNext({
      region:             dbRegion,
      displayRegion:      region,
      intended_city:      region,
      query_region_1:     dbRegion,
      display_region:     region,
      departure_time:     departureTime,
      departure_time_user_selected: departureTimeUserSelected,
      selected_time_band: selectedTimeBand,
      mapped_departure_time: departureTime,
      time_band_night_friendly: isNightFriendlyAnchor(selectedAnchor, selectedTimeBand),
      night_friendly_mode: isNightFriendlyAnchor(selectedAnchor, selectedTimeBand),
      euljiro_mood_label_applied: selectedAnchor.zone_id === 'seoul_euljiro_night',
      euljiro_night_mode_removed: !!selectedAnchor.suppress_night_friendly,
      region_travel_type: 'urban',
      start_lat:          selectedAnchor.center_lat,
      start_lon:          selectedAnchor.center_lon,
      start_anchor:       selectedAnchor.selected_anchor ?? selectedAnchor.name,
      start_anchor_label: selectedAnchor.name,
      zone_id:            selectedAnchor.zone_id ?? null,
      selectedAnchor:     selectedAnchor.selected_anchor ?? selectedAnchor.name,
      selected_anchor_vibe: selectedAnchor.selected_anchor ?? selectedAnchor.name,
      anchor_theme_seed:  selectedAnchor.theme_seed ?? null,
      anchor_district:    selectedAnchor.district ?? null,
      is_curated_vibe_anchor: isSeoulCuratedAnchor(selectedAnchor),
      condition_options_collapsed: isSeoulCuratedAnchor(selectedAnchor),
      default_preset_mode: courseParams?.default_preset_mode !== false,
      _homeAnchor:        selectedAnchor,
    });
  }

  const anchorDisplayName = selectedAnchor ? selectedAnchor.name : null;
  const currentHero = HERO_SLIDES[heroSlideIndex] || HERO_SLIDES[0];
  const heroImage = currentHero?.image || HERO_FALLBACK_IMAGE;

  return (
    <div style={{ minHeight: '100dvh', display: 'flex', flexDirection: 'column', background: '#FFFFFF', position: 'relative', overflow: 'visible' }}>
      <GlobalStyles />

      {/* 히어로 영역 */}
      <div style={{ position: 'relative', height: 'clamp(190px, 28dvh, 260px)', flexShrink: 0, overflow: 'hidden' }}>
        <img
          key={currentHero?.key || 'city'}
          src={heroImage}
          alt="hero"
          style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: '58% center', transition: 'opacity 420ms ease' }}
        />
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(to bottom, transparent 40%, rgba(255,255,255,0.7) 80%, #FFFFFF 100%)',
        }} />
        <div style={{ position: 'absolute', top: 'calc(34px + env(safe-area-inset-top, 0px))', left: 20 }}>
          <p style={{ fontSize: 14, fontWeight: 700, color: '#1F2937', marginBottom: 6 }}>안녕하세요! 👋</p>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: '#111827', margin: 0 }}>어디로 떠나볼까요?</h1>
        </div>
      </div>

      {/* 메인 스크롤 영역 */}
      <div className="hide-scrollbar" style={{
          flex: '1 0 auto', padding: '18px 20px calc(18px + env(safe-area-inset-bottom, 0px))', marginTop: -30,
          background: '#FFFFFF', borderRadius: '28px 28px 0 0', position: 'relative', zIndex: 10
      }}>
        <div style={{ marginBottom: 14 }}>
          <p style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 8, marginLeft: 4 }}>어디로 갈까요?</p>
          <InputCard icon={<PinIcon />} value={region} onTap={() => setRegionSheet(true)} />
        </div>

        <div style={{ marginBottom: 10 }}>
          <div style={{
            border: '1px solid #E2E8F0',
            borderRadius: 16,
            background: 'linear-gradient(180deg, #FFFFFF 0%, #F8FBFF 100%)',
            padding: timeBandExpanded ? 12 : 0,
            boxShadow: '0 2px 12px rgba(0,0,0,0.06)',
            overflow: 'hidden',
          }}>
            <button
              type="button"
              onClick={() => setTimeBandExpanded((value) => !value)}
              aria-expanded={timeBandExpanded}
              style={{
                width: '100%',
                minHeight: 56,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
                padding: timeBandExpanded ? '0 2px 10px' : '0 14px',
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ fontSize: 16, lineHeight: 1.2, fontWeight: 900, color: '#111827' }}>
                  출발 시간대 · {getTimeBandOption(selectedTimeBand).label}
                </span>
              </div>
              <span style={{
                width: 28,
                height: 28,
                borderRadius: 999,
                background: '#EFF6FF',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                transform: timeBandExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                transition: 'transform 160ms ease',
              }}>
                <Chevron color="#2563EB" size={16} />
              </span>
            </button>
            {timeBandExpanded && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
                {TIME_BAND_OPTIONS.map((option) => {
                  const active = selectedTimeBand === option.id;
                  return (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => handleTimeBandSelect(option.id)}
                      aria-pressed={active}
                      style={{
                        minWidth: 0,
                        height: 54,
                        borderRadius: 14,
                        border: active ? '1.5px solid #2563EB' : '1px solid #E5E7EB',
                        background: active ? '#2563EB' : '#FFFFFF',
                        color: active ? '#FFFFFF' : '#334155',
                        cursor: 'pointer',
                        boxShadow: active ? '0 8px 18px rgba(37,99,235,0.18)' : '0 1px 2px rgba(15,23,42,0.04)',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 3,
                      }}
                    >
                      <span style={{ fontSize: 15, lineHeight: 1, fontWeight: 900 }}>{option.label}</span>
                      <span style={{ fontSize: 11, lineHeight: 1.1, fontWeight: 800, color: active ? 'rgba(255,255,255,0.84)' : '#94A3B8' }}>
                        {option.time}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <div style={{ marginBottom: 18 }}>
          <p style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 8, marginLeft: 4 }}>어떤 여행지를 선택할까요?</p>
          <button
            onClick={openDeptSheet}
            style={{
              width: '100%', height: 64, display: 'flex', alignItems: 'center', gap: 14, padding: '0 16px',
              background: '#FFFFFF', borderRadius: 16,
              border: selectedAnchor ? '1.5px solid #2563EB' : '1px solid #F1F5F9',
              boxShadow: '0 2px 12px rgba(0,0,0,0.06)', cursor: 'pointer', textAlign: 'left'
            }}
          >
            <div style={{
              width: 36, height: 36, borderRadius: 10,
              background: selectedAnchor ? '#EFF6FF' : '#F1F5F9',
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
            }}>
              <GreyFlagIcon />
            </div>
            <span style={{ flex: 1, fontSize: 16, fontWeight: 800, color: selectedAnchor ? '#111827' : '#94A3B8' }}>
              {anchorDisplayName ?? '여행지를 선택해주세요'}
            </span>
            <span style={{ fontSize: 14, fontWeight: 700, color: '#2563EB', flexShrink: 0 }}>변경</span>
          </button>
        </div>

        <div style={{
          marginTop: 2,
          padding: '10px 4px calc(2px + env(safe-area-inset-bottom, 0px))',
          borderRadius: 22,
          background: canGenerate ? 'linear-gradient(180deg, rgba(239,246,255,0.88) 0%, rgba(255,255,255,0) 100%)' : 'transparent',
        }}>
          <button onClick={handleNext} disabled={!canGenerate || isGenerating} aria-busy={isGenerating} style={{
            width: '100%', minHeight: 62, borderRadius: 999,
            background: canGenerate ? 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)' : '#CBD5E1',
            color: '#fff', fontSize: 17, fontWeight: 900,
            boxShadow: canGenerate ? '0 12px 26px rgba(37,99,235,0.30), 0 2px 0 rgba(255,255,255,0.18) inset' : 'none',
            border: canGenerate ? '1px solid rgba(255,255,255,0.22)' : 'none',
            cursor: canGenerate && !isGenerating ? 'pointer' : 'not-allowed',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            marginBottom: 0,
            letterSpacing: 0,
            transition: 'box-shadow 160ms ease, transform 160ms ease, background 160ms ease',
            opacity: isGenerating ? 0.92 : 1,
          }}>
            {isGenerating ? '코스 준비 중' : '코스 만들기'}
          </button>
        </div>

      </div>

      {/* 시간 선택 바텀시트 */}
      <BottomSheet open={timeSheet} onClose={() => setTimeSheet(false)} title="출발 시간 선택">
        {(() => {
          const now = new Date();
          const nowH = now.getHours();
          const nowM = now.getMinutes();
          const isToday = selectedDate === '오늘';
          const HOURS = Array.from({ length: 12 }, (_, i) => String(9 + i));   // '9'~'20'
          const MINUTES = ['00', '30'];

          const isHourDisabled = (h) => {
            if (!isToday) return false;
            const hNum = parseInt(h);
            // 해당 시의 :30 도 과거면 비활성
            return hNum < nowH || (hNum === nowH && nowM > 30);
          };
          const isMinuteDisabled = (m) => {
            if (!selectedHour) return true;
            if (!isToday) return false;
            const hNum = parseInt(selectedHour);
            const mNum = parseInt(m);
            return hNum * 60 + mNum < nowH * 60 + nowM;
          };

          return (
            <div className="hide-scrollbar" style={{ padding: '0 20px 20px', overflowY: 'auto', maxHeight: '70dvh' }}>

              {/* 날짜 선택 */}
              <p style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 10 }}>날짜</p>
              <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
                {['오늘', '내일'].map((d) => (
                  <button key={d} onClick={() => setSelectedDate(d)} style={{
                    flex: 1, height: 44, borderRadius: 12, border: 'none', cursor: 'pointer',
                    fontWeight: 700, fontSize: 15,
                    background: selectedDate === d ? '#2563EB' : '#F1F5F9',
                    color: selectedDate === d ? '#FFFFFF' : '#475569',
                  }}>{d}</button>
                ))}
              </div>

              {/* 현재 시간 이후 안내 */}
              {isToday && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 16, padding: '8px 12px', background: '#F0F7FF', borderRadius: 10 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#2563EB' }}>현재 시간 이후부터 선택할 수 있어요.</span>
                </div>
              )}

              {/* 시 선택 */}
              <p style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 10 }}>시간</p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 24 }}>
                {HOURS.map((h) => {
                  const disabled = isHourDisabled(h);
                  const selected = selectedHour === h;
                  return (
                    <button key={h} onClick={() => { if (!disabled) { setSelectedHour(h); if (!selectedMinute) setSelectedMinute('00'); } }} disabled={disabled} style={{
                      height: 44, borderRadius: 12, border: 'none',
                      cursor: disabled ? 'not-allowed' : 'pointer',
                      fontWeight: 700, fontSize: 14,
                      background: selected ? '#2563EB' : '#F1F5F9',
                      color: selected ? '#FFFFFF' : disabled ? '#CBD5E1' : '#475569',
                    }}>{h}시</button>
                  );
                })}
              </div>

              {/* 분 선택 */}
              <p style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 10 }}>분</p>
              <div style={{ display: 'flex', gap: 8, marginBottom: 28 }}>
                {MINUTES.map((m) => {
                  const disabled = isMinuteDisabled(m);
                  const selected = selectedMinute === m;
                  return (
                    <button key={m} onClick={() => !disabled && setSelectedMinute(m)} disabled={disabled} style={{
                      flex: 1, height: 44, borderRadius: 12, border: 'none',
                      cursor: disabled ? 'not-allowed' : 'pointer',
                      fontWeight: 700, fontSize: 15,
                      background: selected ? '#2563EB' : '#F1F5F9',
                      color: selected ? '#FFFFFF' : disabled ? '#CBD5E1' : '#475569',
                    }}>{m}분</button>
                  );
                })}
              </div>

              {/* 완료 버튼 */}
              <button onClick={handleTimeConfirm} disabled={!selectedHour} style={{
                width: '100%', height: 52, borderRadius: 100, border: 'none',
                cursor: selectedHour ? 'pointer' : 'not-allowed',
                background: selectedHour ? '#2563EB' : '#CBD5E1',
                color: '#FFFFFF', fontSize: 16, fontWeight: 800,
                boxShadow: selectedHour ? '0 8px 20px rgba(37,99,235,0.25)' : 'none',
              }}>선택 완료</button>
            </div>
          );
        })()}
      </BottomSheet>

      {/* 지역 선택 바텀시트 */}
      <BottomSheet open={regionSheet} onClose={() => setRegionSheet(false)} title="지역 선택">
        <div className="hide-scrollbar" style={{
          maxHeight: '60dvh',
          overflowY: 'auto',
          padding: '0 20px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px'
        }}>
          {regionList.map((r) => (
            <button key={r} onClick={() => handleRegionSelect(r)}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl ${region === r ? 'bg-blue-50 text-blue-700' : 'bg-gray-50 text-gray-700'}`}
              style={{ border: 'none', cursor: 'pointer' }}>
              <PinIcon />
              <span style={{ fontSize: '14px', fontWeight: 500, flex: 1, textAlign: 'left' }}>{r}</span>
              {region === r && <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M5 12l5 5L20 7" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" /></svg>}
            </button>
          ))}
        </div>
      </BottomSheet>

      {/* 여행지 선택 바텀시트 — 모든 지역 통합 */}
      <BottomSheet
        open={deptSheet}
        onClose={() => setDeptSheet(false)}
        title="여행지 선택"
      >
        <div className="hide-scrollbar" style={{ maxHeight: '70dvh', overflowY: 'auto', padding: '0 20px 30px', display: 'flex', flexDirection: 'column' }}>

          <p style={{ fontSize: 13, fontWeight: 800, color: '#111827', marginBottom: 10, marginLeft: 2 }}>추천 여행지</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7, marginBottom: 22 }}>
            {departuresLoading ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px 0', gap: 8 }}>
                <style>{`@keyframes spin2 { to { transform: rotate(360deg); } }`}</style>
                <div style={{ width: 20, height: 20, border: '2px solid #DBEAFE', borderTopColor: '#2563EB', borderRadius: '50%', animation: 'spin2 0.8s linear infinite' }} />
                <span style={{ fontSize: 13, color: '#94A3B8' }}>불러오는 중...</span>
              </div>
            ) : departures.length === 0 ? (
              <p style={{ fontSize: 13, color: '#CBD5E1', textAlign: 'center', padding: '12px 0' }}>여행지 후보가 없어요</p>
            ) : (
              departures.map((item) => {
                const isSelected = selectedAnchor?.zone_id === item.zone_id;
                return (
                <button
                  key={item.zone_id}
                  onClick={() => {
                    trackEvent('departure_selected', {
                      region: dbRegion,
                      display_region: region,
                      selected_anchor: item.selected_anchor ?? item.name,
                      departure_anchor: item.name,
                      anchor_district: item.district ?? null,
                      vibe: item.selected_anchor ?? item.name,
                      theme: item.theme_seed ?? null,
                      screen: 'home',
                    });
                    setSelectedAnchor(item);
                    setDeptSheet(false);
                    onParamChange('start_anchor', item.selected_anchor ?? item.name);
                    onParamChange('start_anchor_label', item.name);
                    onParamChange('start_lat', item.center_lat);
                    onParamChange('start_lon', item.center_lon);
                    onParamChange('zone_id', item.zone_id ?? null);
                    onParamChange('selected_anchor_vibe', item.selected_anchor ?? item.name);
                    onParamChange('anchor_theme_seed', item.theme_seed ?? null);
                    onParamChange('anchor_district', item.district ?? null);
                    onParamChange('is_curated_vibe_anchor', isSeoulCuratedAnchor(item));
                    onParamChange('condition_options_collapsed', isSeoulCuratedAnchor(item));
                    onParamChange('default_preset_mode', true);
                    onParamChange('time_band_night_friendly', isNightFriendlyAnchor(item, selectedTimeBand));
                    onParamChange('night_friendly_mode', isNightFriendlyAnchor(item, selectedTimeBand));
                    onParamChange('euljiro_mood_label_applied', item.zone_id === 'seoul_euljiro_night');
                    onParamChange('euljiro_night_mode_removed', !!item.suppress_night_friendly);
                    const seededMood = moodFromAnchorSeed(item);
                    if (seededMood) {
                      onParamChange('mood', seededMood);
                      onParamChange('mood_seeded_by_anchor', true);
                    } else {
                      onParamChange('mood_seeded_by_anchor', false);
                    }
                    onParamChange('_homeAnchor', item);
                  }}
                  aria-pressed={isSelected}
                  style={{
                    position: 'relative',
                    minHeight: 66,
                    display: 'flex',
                    alignItems: 'center',
                    padding: '12px 14px',
                    background: isSelected ? 'linear-gradient(180deg, #EFF6FF 0%, #FFFFFF 100%)' : '#FFFFFF',
                    borderRadius: 16,
                    border: isSelected ? '1.5px solid #2563EB' : '1px solid #EEF2F7',
                    boxShadow: isSelected ? '0 8px 20px rgba(37,99,235,0.10)' : '0 2px 10px rgba(15,23,42,0.035)',
                    gap: 11,
                    cursor: 'pointer',
                    textAlign: 'left',
                    overflow: 'hidden',
                  }}
                >
                  {isSelected && (
                    <span
                      aria-hidden="true"
                      style={{
                        position: 'absolute',
                        left: 0,
                        top: 12,
                        bottom: 12,
                        width: 3,
                        borderRadius: '0 999px 999px 0',
                        background: '#2563EB',
                      }}
                    />
                  )}
                  <div style={{
                    width: 34, height: 34, borderRadius: 11,
                    background: isSelected ? '#DBEAFE' : '#F8FAFC',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                  }}>
                    <PinIcon />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ margin: 0, fontSize: 15, lineHeight: 1.2, fontWeight: 800, color: '#1F2937', wordBreak: 'keep-all', overflowWrap: 'anywhere' }}>{item.name}</p>
                    {(item.vibe_label || item.district) && (
                      <p style={{ margin: '3px 0 0', fontSize: 12, fontWeight: 600, color: '#64748B', lineHeight: 1.32, wordBreak: 'keep-all', overflowWrap: 'anywhere' }}>
                        {[item.district, item.vibe_label].filter(Boolean).join(' · ')}
                      </p>
                    )}
                    {moodFromAnchorSeed(item) && (
                      <p style={{ margin: '3px 0 0', fontSize: 11, lineHeight: 1.25, fontWeight: 700, color: isSelected ? '#1D4ED8' : '#64748B', wordBreak: 'keep-all' }}>
                        기본 분위기 · {moodFromAnchorSeed(item)}
                      </p>
                    )}
                    {(item.tourist_count != null || item.meal_count != null) && (
                      <p style={{ margin: '2px 0 0', fontSize: 11, lineHeight: 1.25, color: '#94A3B8', wordBreak: 'keep-all' }}>
                        {[
                          item.tourist_count != null && `관광지 ${item.tourist_count}개`,
                          item.meal_count    != null && `식당 ${item.meal_count}개`,
                          item.cafe_count    != null && `카페 ${item.cafe_count}개`,
                        ].filter(Boolean).join(' · ')}
                      </p>
                    )}
                  </div>
                  {isSelected && (
                    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
                      <path d="M5 12l5 5L20 7" stroke="#2563EB" strokeWidth="2.5" strokeLinecap="round"/>
                    </svg>
                  )}
                </button>
                );
              })
            )}
          </div>

          <div style={{ background: '#F0F7FF', borderRadius: 12, padding: 14, display: 'flex', gap: 10 }}>
            <div style={{ width: 18, height: 18, background: '#2563EB', borderRadius: 100, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <span style={{ color: '#FFF', fontSize: 10, fontWeight: 900 }}>i</span>
            </div>
            <div>
              <p style={{ margin: '0 0 4px', fontSize: 13, fontWeight: 700, color: '#1F2937' }}>여행지 선택 안내</p>
              <p style={{ margin: 0, fontSize: 12, color: '#64748B', lineHeight: 1.45, wordBreak: 'keep-all' }}>
                대표 관광지와 인기 여행 흐름을 중심으로 추천해드려요
              </p>
            </div>
          </div>
        </div>
      </BottomSheet>
    </div>
  );
}
