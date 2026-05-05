import { useState, useEffect } from 'react';
import BottomSheet from '../../components/common/BottomSheet';
import {
  REGIONS, REGION_TO_DB, getHeroImage,
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
/* 프로젝트의 탭바 클래스명이나 ID가 다를 수 있어 최대한 포괄적으로 잡았습니다 */
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

/* ─── 3. 입력 카드 컴포넌트 ────────────────────────── */
function InputCard({ icon, value, onTap }) {
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
      <span style={{ flex: 1, fontSize: 16, fontWeight: 800, color: '#111827' }}>{value}</span>
      <span style={{ fontSize: 14, fontWeight: 700, color: '#2563EB', flexShrink: 0 }}>변경</span>
    </button>
  );
}

/* ─── 4. 홈 스크린 메인 ────────────────────────────── */
export default function HomeScreen({ onNext }) {
  const [region, setRegion] = useState('서울');
  const [departureText, setDepartureText] = useState(''); 
  const [regionSheet, setRegionSheet] = useState(false);
  const [deptSheet, setDeptSheet] = useState(false);

  // 🔥 탭바 강제 제어를 위한 useEffect 추가 (바텀시트 열릴 때 body에 클래스 추가)
  useEffect(() => {
    if (regionSheet || deptSheet) {
      document.body.classList.add('sheet-is-open');
    } else {
      document.body.classList.remove('sheet-is-open');
    }
    
    // 컴포넌트 언마운트 시 안전하게 클래스 제거
    return () => {
      document.body.classList.remove('sheet-is-open');
    };
  }, [regionSheet, deptSheet]);

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
          <p style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 8, marginLeft: 4 }}>언제 출발할까요?</p>
          <InputCard icon={<ClockIcon />} value="오늘 10:00" onTap={() => {}} />
        </div>

        <div style={{ marginBottom: 32 }}>
          <p style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 8, marginLeft: 4 }}>어느 지역 주변을 돌까요?</p>
          <div style={{
            width: '100%', height: 64, display: 'flex', alignItems: 'center', gap: 14, padding: '0 16px',
            background: '#FFFFFF', borderRadius: 16, border: '1px solid #F1F5F9', boxShadow: '0 2px 12px rgba(0,0,0,0.06)', position: 'relative'
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10, background: '#F1F5F9',
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
            }}>
              <GreyFlagIcon />
            </div>
            <input 
              type="text" 
              placeholder="선택 안 함" 
              value={departureText}
              onChange={(e) => setDepartureText(e.target.value)}
              style={{ flex: 1, border: 'none', outline: 'none', fontSize: 16, fontWeight: 800, color: '#111827', background: 'transparent' }}
            />
            <button 
              onClick={() => setDeptSheet(true)} 
              style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', display: 'flex', alignItems: 'center' }}
            >
              <BlueSearchIcon />
            </button>
          </div>
        </div>

        <div style={{ padding: '0 4px' }}>
          <button onClick={onNext} style={{
            width: '100%', height: 58, borderRadius: 100, background: '#2563EB', color: '#fff', fontSize: 18, fontWeight: 800,
            boxShadow: '0 8px 20px rgba(37,99,235,0.25)', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 40
          }}>
            코스 만들기
          </button>
        </div>

        <div style={{ height: 1, background: '#F1F5F9', marginBottom: 24 }} />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <p style={{ fontSize: 15, fontWeight: 700, color: '#111827', margin: 0 }}>최근 조건으로 다시 만들기</p>
          <Chevron color="#94A3B8" size={16} />
        </div>

        <button style={{
          width: '100%', display: 'flex', alignItems: 'center', padding: '12px', background: '#FFFFFF',
          borderRadius: 16, border: '1px solid #F1F5F9', boxShadow: '0 2px 12px rgba(0,0,0,0.05)', gap: 14, textAlign: 'left'
        }}>
          <div style={{ width: 56, height: 56, borderRadius: 12, background: '#F1F5F9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ fontSize: 24 }}>🗺️</span>
          </div>
          <div style={{ flex: 1 }}>
            <span style={{ display: 'block', fontSize: 14, fontWeight: 700, color: '#111827', marginBottom: 4 }}>
              최근 코스 없음
            </span>
            <span style={{ display: 'block', fontSize: 12, fontWeight: 500, color: '#64748B' }}>
              새 코스를 만들어 보세요
            </span>
          </div>
        </button>
      </div>

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
          {REGIONS.map((r) => (
            <button key={r} onClick={() => { setRegion(r); setRegionSheet(false); }}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl ${region === r ? 'bg-blue-50 text-blue-700' : 'bg-gray-50 text-gray-700'}`}
              style={{ border: 'none', cursor: 'pointer' }}>
              <PinIcon />
              <span style={{ fontSize: '14px', fontWeight: 500, flex: 1, textAlign: 'left' }}>{r}</span>
              {region === r && <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M5 12l5 5L20 7" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" /></svg>}
            </button>
          ))}
        </div>
      </BottomSheet>

      {/* 출발 기준점 선택 바텀시트 */}
      <BottomSheet 
        open={deptSheet} 
        onClose={() => { setDeptSheet(false); }}
        title="출발 기준점 선택"
      >
        <div className="hide-scrollbar" 
          style={{ 
            maxHeight: '70vh', 
            overflowY: 'auto',
            padding: '0 20px 30px',
            display: 'flex',
            flexDirection: 'column',
            msOverflowStyle: 'none', 
            scrollbarWidth: 'none'
          }}>
          
          {/* ✅ 2. 현재 위치 사용 카드 강조 약화 */}
          <div style={{ background: '#F8FAFC', border: '1px solid #F1F5F9', borderRadius: 12, padding: 16, marginBottom: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="#94A3B8">
                <path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z" />
              </svg>
              <div>
                <p style={{ margin: 0, fontSize: 14, fontWeight: 600, color: '#475569' }}>현재 위치 사용</p>
                <p style={{ margin: 0, fontSize: 12, color: '#94A3B8' }}>서울 중구 을지로</p>
              </div>
            </div>
            
            {/* ✅ 3. 지역 불일치 경고 박스 축소 */}
            <div style={{ background: '#FFFFFF', borderRadius: 8, padding: '8px 10px', display: 'flex', alignItems: 'center', gap: 6, border: '1px solid #E2E8F0' }}>
              <span style={{ fontSize: 12 }}>⚠️</span>
              <p style={{ margin: 0, fontSize: 11, fontWeight: 500, color: '#64748B', lineHeight: 1.3 }}>
                현재 위치는 선택한 지역(서울)과 다릅니다. <span style={{ color: '#94A3B8' }}>서울 내에서 선택해주세요.</span>
              </p>
            </div>
          </div>

          <p style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 12 }}>인기 출발 기준점</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
            {[
              { name: '서울역', loc: '중구' },
              { name: '강남역', loc: '강남구' },
              { name: '홍대입구역', loc: '마포구' },
              { name: '잠실역', loc: '송파구' },
              { name: '성수동 카페거리', loc: '성동구' },
            ].map((item, idx) => (
              <button 
                key={idx} 
                onClick={() => { setDepartureText(item.name); setDeptSheet(false); }}
                style={{
                  display: 'flex', alignItems: 'center', padding: '12px 16px', background: '#FFFFFF',
                  borderRadius: 12, border: '1px solid #F1F5F9', gap: 12, cursor: 'pointer'
                }}
              >
                <div style={{ width: 32, height: 32, background: '#F8FAFC', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 14 }}>🚇</span>
                </div>
                <div style={{ flex: 1, textAlign: 'left' }}>
                  <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#1F2937' }}>{item.name}</p>
                  <p style={{ margin: 0, fontSize: 12, color: '#94A3B8' }}>{item.loc}</p>
                </div>
                {/* ✅ 1. 우측 km 거리 표시 완전히 삭제됨 */}
              </button>
            ))}
          </div>

          <p style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 12 }}>직접 검색</p>
          <div style={{ 
            position: 'relative', display: 'flex', alignItems: 'center', 
            background: '#F8FAFC', borderRadius: 12, padding: '0 16px', height: 52, marginBottom: 8,
            border: '1px solid #E2E8F0'
          }}>
            <input 
              placeholder="동, 역, 랜드마크로 검색" 
              style={{ flex: 1, border: 'none', background: 'transparent', outline: 'none', fontSize: 14, color: '#1F2937' }}
            />
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </div>
          <p style={{ fontSize: 12, color: '#94A3B8', marginBottom: 24, marginLeft: 4 }}>동/역/랜드마크만 검색할 수 있습니다.</p>

          <div style={{ background: '#F0F7FF', borderRadius: 12, padding: 14, display: 'flex', gap: 10 }}>
            <div style={{ width: 18, height: 18, background: '#2563EB', borderRadius: 100, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <span style={{ color: '#FFF', fontSize: 10, fontWeight: 900 }}>i</span>
            </div>
            <div>
              <p style={{ margin: '0 0 4px', fontSize: 13, fontWeight: 700, color: '#1F2937' }}>검색 가능한 기준점</p>
              <p style={{ margin: 0, fontSize: 12, color: '#64748B', lineHeight: 1.4 }}>예시) 성수동, 강남역, 경복궁, 잠실역, 더현대 서울</p>
            </div>
          </div>
        </div>
      </BottomSheet>
    </div>
  );
}