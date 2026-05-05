import { useState, useEffect } from 'react';
import BottomSheet from '../../components/common/BottomSheet';
import {
  REGIONS, REGION_TO_DB, getHeroImage, STATIC_ANCHORS,
} from '../../data/dayTripDummyData';

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

  // departure_time 문자열 "오늘 9:00" 파싱 → 시트 선택기 초기값 복원
  const _parsedTime = (() => {
    const m = courseParams?.departure_time?.match(/^(오늘|내일)\s+(\d+):(\d{2})/);
    return m ? { date: m[1], hour: m[2], minute: m[3] } : null;
  })();
  const [departureTime, setDepartureTime] = useState(courseParams?.departure_time || null);
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

  function handleTimeConfirm() {
    if (!selectedHour) return;
    const time = `${selectedDate} ${selectedHour}:${selectedMinute}`;
    setDepartureTime(time);
    onParamChange('departure_time', time);
    setTimeSheet(false);
  }

  function handleRegionSelect(r) {
    const db = REGION_TO_DB[r] ?? r;
    setRegion(r);
    setSelectedAnchor(null);
    setDepartures([]);
    setRegionSheet(false);
    onParamChange('displayRegion', r);
    onParamChange('region', db);
    onParamChange('start_anchor', null);
    onParamChange('start_lat', null);
    onParamChange('start_lon', null);
    onParamChange('zone_id', null);
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
          setDepartures(list);
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
    if (!canGenerate) return;
    onNext({
      region:             dbRegion,
      displayRegion:      region,
      departure_time:     departureTime,
      region_travel_type: 'urban',
      start_lat:          selectedAnchor.center_lat,
      start_lon:          selectedAnchor.center_lon,
      start_anchor:       selectedAnchor.name,
      zone_id:            selectedAnchor.zone_id ?? null,
      _homeAnchor:        selectedAnchor,
    });
  }

  const anchorDisplayName = selectedAnchor ? selectedAnchor.name : null;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#FFFFFF', position: 'relative', overflow: 'hidden' }}>
      <GlobalStyles />

      {/* 히어로 영역 */}
      <div style={{ position: 'relative', height: 260, flexShrink: 0, overflow: 'hidden' }}>
        <img
          src={getHeroImage(region)}
          alt="hero"
          style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: '58% center' }}
        />
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(to bottom, transparent 40%, rgba(255,255,255,0.7) 80%, #FFFFFF 100%)',
        }} />
        <div style={{ position: 'absolute', top: 52, left: 20 }}>
          <p style={{ fontSize: 14, fontWeight: 700, color: '#1F2937', marginBottom: 6 }}>안녕하세요! 👋</p>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: '#111827', margin: 0 }}>어디로 떠나볼까요?</h1>
        </div>
      </div>

      {/* 메인 스크롤 영역 */}
      <div className="hide-scrollbar" style={{
          flex: 1, overflowY: 'auto', padding: '24px 20px 40px', marginTop: -30,
          background: '#FFFFFF', borderRadius: '28px 28px 0 0', position: 'relative', zIndex: 10, WebkitOverflowScrolling: 'touch'
      }}>
        <div style={{ marginBottom: 20 }}>
          <p style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 8, marginLeft: 4 }}>어디로 갈까요?</p>
          <InputCard icon={<PinIcon />} value={region} onTap={() => setRegionSheet(true)} />
        </div>

        <div style={{ marginBottom: 20 }}>
          <p style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 8, marginLeft: 4 }}>오늘 코스, 몇 시에 시작할까요?</p>
          <InputCard icon={<ClockIcon />} value={departureTime} placeholder="출발 시간을 선택해주세요" onTap={() => setTimeSheet(true)} />
        </div>

        <div style={{ marginBottom: 32 }}>
          <p style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 8, marginLeft: 4 }}>어느 지역 주변을 돌까요?</p>
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
              {anchorDisplayName ?? '출발 기준점을 선택해주세요'}
            </span>
            <span style={{ fontSize: 14, fontWeight: 700, color: '#2563EB', flexShrink: 0 }}>변경</span>
          </button>
        </div>

        <div style={{ padding: '0 4px' }}>
          <button onClick={handleNext} disabled={!canGenerate} style={{
            width: '100%', height: 58, borderRadius: 100,
            background: canGenerate ? '#2563EB' : '#CBD5E1',
            color: '#fff', fontSize: 18, fontWeight: 800,
            boxShadow: canGenerate ? '0 8px 20px rgba(37,99,235,0.25)' : 'none',
            border: 'none', cursor: canGenerate ? 'pointer' : 'not-allowed',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 40
          }}>
            코스 만들기
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
            <div className="hide-scrollbar" style={{ padding: '0 20px 20px', overflowY: 'auto', maxHeight: '70vh' }}>

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
          maxHeight: '60vh',
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

      {/* 출발 기준점 선택 바텀시트 — 모든 지역 통합 */}
      <BottomSheet
        open={deptSheet}
        onClose={() => setDeptSheet(false)}
        title="출발 기준점 선택"
      >
        <div className="hide-scrollbar" style={{ maxHeight: '70vh', overflowY: 'auto', padding: '0 20px 30px', display: 'flex', flexDirection: 'column' }}>

          <p style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 12 }}>추천 출발 기준점</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
            {departuresLoading ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px 0', gap: 8 }}>
                <style>{`@keyframes spin2 { to { transform: rotate(360deg); } }`}</style>
                <div style={{ width: 20, height: 20, border: '2px solid #DBEAFE', borderTopColor: '#2563EB', borderRadius: '50%', animation: 'spin2 0.8s linear infinite' }} />
                <span style={{ fontSize: 13, color: '#94A3B8' }}>불러오는 중...</span>
              </div>
            ) : departures.length === 0 ? (
              <p style={{ fontSize: 13, color: '#CBD5E1', textAlign: 'center', padding: '12px 0' }}>출발 기준점 후보가 없어요</p>
            ) : (
              departures.map((item) => (
                <button
                  key={item.zone_id}
                  onClick={() => {
                    setSelectedAnchor(item);
                    setDeptSheet(false);
                    onParamChange('start_anchor', item.name);
                    onParamChange('start_lat', item.center_lat);
                    onParamChange('start_lon', item.center_lon);
                    onParamChange('zone_id', item.zone_id ?? null);
                    onParamChange('_homeAnchor', item);
                  }}
                  style={{
                    display: 'flex', alignItems: 'center', padding: '14px 16px',
                    background: selectedAnchor?.zone_id === item.zone_id ? '#EFF6FF' : '#FFFFFF',
                    borderRadius: 14,
                    border: selectedAnchor?.zone_id === item.zone_id ? '1.5px solid #2563EB' : '1px solid #F1F5F9',
                    gap: 12, cursor: 'pointer', textAlign: 'left'
                  }}
                >
                  <div style={{
                    width: 36, height: 36, borderRadius: 10,
                    background: selectedAnchor?.zone_id === item.zone_id ? '#DBEAFE' : '#F1F5F9',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                  }}>
                    <PinIcon />
                  </div>
                  <div style={{ flex: 1 }}>
                    <p style={{ margin: 0, fontSize: 15, fontWeight: 700, color: '#1F2937' }}>{item.name}</p>
                    {(item.tourist_count != null || item.meal_count != null) && (
                      <p style={{ margin: '2px 0 0', fontSize: 11, color: '#94A3B8' }}>
                        {[
                          item.tourist_count != null && `관광지 ${item.tourist_count}개`,
                          item.meal_count    != null && `식당 ${item.meal_count}개`,
                          item.cafe_count    != null && `카페 ${item.cafe_count}개`,
                        ].filter(Boolean).join(' · ')}
                      </p>
                    )}
                  </div>
                  {selectedAnchor?.zone_id === item.zone_id && (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                      <path d="M5 12l5 5L20 7" stroke="#2563EB" strokeWidth="2.5" strokeLinecap="round"/>
                    </svg>
                  )}
                </button>
              ))
            )}
          </div>

          <div style={{ background: '#F0F7FF', borderRadius: 12, padding: 14, display: 'flex', gap: 10 }}>
            <div style={{ width: 18, height: 18, background: '#2563EB', borderRadius: 100, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <span style={{ color: '#FFF', fontSize: 10, fontWeight: 900 }}>i</span>
            </div>
            <div>
              <p style={{ margin: '0 0 4px', fontSize: 13, fontWeight: 700, color: '#1F2937' }}>출발 기준점 안내</p>
              <p style={{ margin: 0, fontSize: 12, color: '#64748B', lineHeight: 1.4 }}>선택한 기준점 주변에서 당일치기 코스를 구성합니다.</p>
            </div>
          </div>
        </div>
      </BottomSheet>
    </div>
  );
}
