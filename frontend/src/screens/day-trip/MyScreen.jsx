import { useState } from 'react';

/* ─── SVG 아이콘 ──────────────────────────────────── */
const ChevronRight = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-[#CBD5E1]">
    <path d="M9 18l6-6-6-6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const HeartIcon = ({ filled }) => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill={filled ? "#EF4444" : "none"} stroke={filled ? "#EF4444" : "#CBD5E1"} strokeWidth="2">
    <path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z" />
  </svg>
);

/* ─── 메인 컴포넌트 ───────────────────────────────── */
export default function MyScreen({ onGoHome }) {
  const [savedCourses] = useState([]);
  const [recentCourses] = useState([]);

  return (
    <div className="bg-white min-h-screen flex flex-col relative">

      {/* ─── 헤더 영역 ─── */}
      <div className="px-5 pt-8 pb-6 bg-white sticky top-0 z-20">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-[#EFF6FF] flex items-center justify-center text-[24px]">
              🧳
            </div>
            <div>
              <p className="text-[18px] font-extrabold text-[#111827]">여행자님</p>
              <p className="text-[13px] text-[#64748B] font-medium">안녕하세요! 즐거운 여행 되세요.</p>
            </div>
          </div>
          <button className="p-2 bg-[#F8FAFC] rounded-full border border-[#F1F5F9]">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" stroke="#4B5563" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <circle cx="12" cy="12" r="3" stroke="#4B5563" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
      </div>

      {/* ─── 본문 영역 ─── */}
      <div className="flex-1 px-5 pb-[200px]">

        <div className="mt-4 mb-8">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-[17px] font-extrabold text-[#111827]">저장한 코스</h3>
          </div>
          {savedCourses.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 bg-[#F8FAFC] rounded-[20px] gap-2">
              <span className="text-[32px]">🗺️</span>
              <p className="text-[14px] font-semibold text-[#94A3B8]">아직 저장한 코스가 없어요</p>
              <p className="text-[12px] text-[#CBD5E1]">마음에 드는 코스를 저장해 보세요</p>
            </div>
          ) : (
            <div className="flex flex-col gap-3.5">
              {savedCourses.map((course) => (
                <div key={course.id} className="bg-white rounded-[20px] border border-[#F1F5F9] shadow-[0_2px_12px_rgba(0,0,0,0.03)] p-4 flex items-center gap-4">
                  {course.image
                    ? <img src={course.image} alt="" className="w-16 h-16 rounded-2xl object-cover shrink-0" />
                    : <div className="w-16 h-16 rounded-2xl bg-[#F1F5F9] shrink-0" />
                  }
                  <div className="flex-1 min-w-0">
                    <p className="text-[15px] font-bold text-[#1F2937] truncate mb-1">{course.title}</p>
                    <p className="text-[12px] text-[#94A3B8] font-medium">{course.location} · {course.time}</p>
                  </div>
                  <HeartIcon filled />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="mb-8">
          <h3 className="text-[17px] font-extrabold text-[#111827] mb-4">최근 본 코스</h3>
          {recentCourses.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 bg-[#F8FAFC] rounded-[20px] gap-2">
              <span className="text-[28px]">🕐</span>
              <p className="text-[13px] font-semibold text-[#94A3B8]">최근 본 코스가 없어요</p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {recentCourses.map((course) => (
                <div key={course.id} className="flex items-center justify-between py-1 px-1">
                  <div className="flex items-center gap-3.5">
                    {course.image
                      ? <img src={course.image} alt="" className="w-12 h-12 rounded-[14px] object-cover" />
                      : <div className="w-12 h-12 rounded-[14px] bg-[#F1F5F9]" />
                    }
                    <div>
                      <p className="text-[14px] font-bold text-[#1F2937] mb-0.5">{course.title}</p>
                      <p className="text-[11px] text-[#94A3B8] font-medium">{course.location} · {course.time}</p>
                    </div>
                  </div>
                  <ChevronRight />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ─── 하단 고정 추천 카드 ─── */}
      <div className="fixed bottom-[104px] left-0 right-0 px-5 z-20">
        <button
          onClick={onGoHome}
          className="w-full flex items-center justify-between bg-[#F0F7FF] border border-[#D1E9FF] rounded-[24px] px-6 py-5 text-left shadow-[0_4px_20px_rgba(37,99,235,0.1)] active:scale-[0.97] transition-all"
        >
          <div className="flex flex-col gap-1">
            <h4 className="text-[16px] font-extrabold text-[#1E3A8A]">새로운 코스 만들기</h4>
            <p className="text-[12px] font-bold text-[#2563EB] opacity-80">지금 바로 떠나볼까요? ✨</p>
          </div>
          <span className="text-[38px] drop-shadow-sm ml-2">🗺️</span>
        </button>
      </div>

    </div>
  );
}
