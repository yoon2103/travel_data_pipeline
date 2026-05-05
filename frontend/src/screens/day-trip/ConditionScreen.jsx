import { useState } from 'react';
import { MOODS, WALK_LEVELS, DENSITY_LEVELS } from '../../data/dayTripDummyData';

/* ─── 애니메이션 스타일 정의 ─── */
const animationStyle = `
  @keyframes sparkle {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.3); opacity: 0.6; }
  }
  .animate-sparkle {
    animation: sparkle 2s infinite ease-in-out;
  }
`;

/* ─── SVG 아이콘 ──────────────────────────────────── */
const BackIcon = () => ( <svg width="24" height="24" viewBox="0 0 24 24" fill="none"> <path d="M15 18l-6-6 6-6" stroke="#111827" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/> </svg> );
const NatureIcon = () => ( <svg width="20" height="20" viewBox="0 0 24 24" fill="#1E3A8A"> <path d="M14 6c0-1.66-1.34-3-3-3S8 4.34 8 6s1.34 3 3 3 3-1.34 3-3zm5.94 13.12L14 9.5c-.34-.4-1.12-.4-1.46 0l-5.4 6.35c-.43.51-.07 1.3.6 1.3h12.2c.67 0 1.03-.79.6-1.3z" opacity="0.8"/> <path d="M5 19h14c.67 0 1.03-.79.6-1.3L14 9.5c-.34-.4-1.12-.4-1.46 0L4.4 17.7c-.43.51-.07 1.3.6 1.3z" fill="#2563EB"/> </svg> );
const PinIcon = () => ( <svg width="20" height="20" viewBox="0 0 24 24" fill="none"> <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" fill="#E0E7FF" stroke="#D97706" strokeWidth="1.5" /> <circle cx="12" cy="9" r="2.5" fill="#1E3A8A" /> <path d="M9 22h6" stroke="#D97706" strokeWidth="2" strokeLinecap="round" /> </svg> );
const CalendarIcon = () => ( <svg width="20" height="20" viewBox="0 0 24 24" fill="#2563EB"> <path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2zm-7 5h5v5h-5z"/> </svg> );

const ChevronIcon = ({ isOpen }) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" style={{ transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>
    <path d="M9 18l6-6-6-6" stroke="#9CA3AF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const CheckIcon = () => ( <svg width="18" height="18" viewBox="0 0 24 24" fill="none"> <path d="M5 13l4 4L19 7" stroke="#2563EB" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/> </svg> );

/* ─── 아코디언 카드 컴포넌트 ──────────────────────── */
function AccordionCard({ id, icon, label, value, options, isOpen, onToggle, onSelect }) {
  return (
    <div className={`w-full bg-white rounded-[18px] border border-[#F1F5F9] overflow-hidden transition-all duration-300 ${isOpen ? 'shadow-[0_8px_20px_rgba(0,0,0,0.06)]' : 'shadow-[0_2px_8px_rgba(0,0,0,0.04)]'}`}>
      <button onClick={() => onToggle(id)} className="w-full flex items-center justify-between px-5 py-4.5 bg-white active:bg-gray-50 transition-colors">
        <div className="flex items-center gap-3.5">
          {icon}
          <span className="text-[15px] font-bold text-[#1F2937]">{label}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[14px] font-semibold text-[#2563EB]">{value}</span>
          <ChevronIcon isOpen={isOpen} />
        </div>
      </button>
      {isOpen && (
        <div className="px-3 pb-3 pt-1">
          <div className="w-full h-[1px] bg-[#F1F5F9] mb-2" />
          <div className="flex flex-col gap-1">
            {options.map((opt) => (
              <button key={opt} onClick={() => onSelect(id, opt)} className={`flex items-center justify-between px-4 py-3 rounded-xl transition-colors ${value === opt ? 'bg-blue-50 text-[#2563EB] font-bold' : 'bg-transparent text-[#475569] active:bg-gray-50'}`}>
                <span className="text-[14px] font-medium">{opt}</span>
                {value === opt && <CheckIcon />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── 메인 컴포넌트 ───────────────────────────────── */
export default function ConditionScreen({ onBack, onNext, courseParams, onParamChange }) {
  const [openAccordionId, setOpenAccordionId] = useState(null);

  const handleToggle = (id) => setOpenAccordionId(openAccordionId === id ? null : id);

  const handleSelect = (key, value) => {
    onParamChange(key, value);
    setOpenAccordionId(null);
  };

  return (
    <div className="bg-white min-h-screen flex flex-col relative">
      <style>{animationStyle}</style>

      {/* 헤더 */}
      <div className="flex items-center justify-between px-4 py-4 bg-white sticky top-0 z-20">
        <button onClick={onBack} className="p-1 -ml-1"><BackIcon /></button>
        <h2 className="text-[16px] font-bold text-[#111827]">조건 선택</h2>
        <button className="text-[14px] font-medium text-[#6B7280]">초기화</button>
      </div>

      {/* 본문 */}
      <div className="px-5 pt-4 pb-48">
        <section className="mb-8">
          <h3 className="text-[15px] font-bold text-[#111827] mb-4">기본 설정</h3>
          <div className="flex flex-col gap-3.5">
            <AccordionCard
              id="mood"
              icon={<NatureIcon />}
              label="어떤 분위기?"
              value={courseParams.mood || ""}
              options={MOODS}
              isOpen={openAccordionId === 'mood'}
              onToggle={handleToggle}
              onSelect={handleSelect}
            />
            <AccordionCard
              id="walk"
              icon={<PinIcon />}
              label="거리 부담은?"
              value={courseParams.walk || ""}
              options={WALK_LEVELS}
              isOpen={openAccordionId === 'walk'}
              onToggle={handleToggle}
              onSelect={handleSelect}
            />
            <AccordionCard
              id="density"
              icon={<CalendarIcon />}
              label="일정은?"
              value={courseParams.density || ""}
              options={DENSITY_LEVELS}
              isOpen={openAccordionId === 'density'}
              onToggle={handleToggle}
              onSelect={handleSelect}
            />
          </div>
        </section>

        {/* 준비 완료 요약 카드 */}
        <section className="mt-10 px-1">
          <div className="flex flex-col items-center justify-center bg-[#F7FAFF] rounded-[30px] p-8 border border-[#E8F2FF] shadow-sm relative overflow-hidden">
            <div className="flex gap-1 mb-3">
              <span className="text-[20px] animate-sparkle" style={{ animationDelay: '0s' }}>✨</span>
              <span className="text-[14px] font-extrabold text-[#2563EB] pt-1">준비 완료!</span>
              <span className="text-[20px] animate-sparkle" style={{ animationDelay: '0.5s' }}>✨</span>
            </div>
            <h3 className="text-[18px] font-bold text-[#111827] text-center mb-5 leading-snug">
              선택하신 조건에 맞춰<br/>최적의 코스를 추천해 드릴게요
            </h3>
            <div className="flex flex-wrap justify-center gap-2">
              {[courseParams.walk, courseParams.density].filter(Boolean).map((text) => (
                <span key={text} className="px-3.5 py-1.5 bg-white text-[#475569] text-[12px] font-bold rounded-full border border-blue-50 shadow-[0_2px_4px_rgba(0,0,0,0.02)]">
                  {text}
                </span>
              ))}
            </div>
            <p className="mt-5 text-[11px] text-[#94A3B8] font-medium italic">"잠시만 기다려 주세요!"</p>
          </div>
        </section>
      </div>

      {/* 하단 버튼 */}
      <div className="fixed bottom-14 left-6 right-6 z-20">
        <button
          onClick={() => onNext()}
          className="w-full h-[56px] bg-[#2563EB] text-white font-bold text-[16px] rounded-full shadow-[0_8px_20px_rgba(37,99,235,0.4)] active:scale-[0.98] transition-transform"
        >
          이 조건으로 코스 만들기
        </button>
      </div>
    </div>
  );
}
