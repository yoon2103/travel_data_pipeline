import { useState } from 'react';

const ROLE_LABEL = {
  cafe:    '분위기 좋은 카페',
  meal:    '인기 맛집',
  spot:    '대표 관광지',
  culture: '문화/전시 공간',
};

export default function CourseEditScreen({ initialPlaces = [], onBack, onDone }) {
  const [places, setPlaces] = useState(initialPlaces);
  const [editMode, setEditMode] = useState(false);

  function handleDelete(id) {
    setPlaces((prev) => prev.filter((p) => p.id !== id));
  }

  function moveUp(index) {
    if (index === 0) return;
    const next = [...places];
    [next[index - 1], next[index]] = [next[index], next[index - 1]];
    setPlaces(next);
  }

  function moveDown(index) {
    if (index === places.length - 1) return;
    const next = [...places];
    [next[index], next[index + 1]] = [next[index + 1], next[index]];
    setPlaces(next);
  }

  const totalMin = places.reduce((acc, p) => {
    const m = (p.duration || '').match(/(?:(\d+)시간)?(?:\s*(\d+)분)?/);
    return acc + (parseInt(m?.[1] || 0)) * 60 + parseInt(m?.[2] || 0);
  }, 0);
  const totalH = Math.floor(totalMin / 60);
  const totalM = totalMin % 60;
  const overTime = totalMin > 480;

  return (
    <div className="bg-[#f0f4f8] min-h-full">
      {/* 헤더 */}
      <div className="bg-white px-5 pt-2 pb-3 flex items-center justify-between shadow-sm">
        <button onClick={onBack} className="p-1 -ml-1">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path d="M15 18l-6-6 6-6" stroke="#374151" strokeWidth="2" strokeLinecap="round"/>
          </svg>
        </button>
        <h2 className="text-[15px] font-semibold text-gray-900">일정 편집</h2>
        <button
          onClick={() => { if (editMode) { onDone?.(); } else { setEditMode(true); } }}
          className={`text-[13px] font-semibold ${editMode ? 'text-blue-600' : 'text-gray-500'}`}
        >
          {editMode ? '완료' : '편집'}
        </button>
      </div>

      <div className="px-4 pt-3 pb-32 flex flex-col gap-2.5">

        {/* 총 시간 요약 */}
        <div className="bg-white rounded-xl shadow-sm px-4 py-3 flex items-center justify-between">
          <div>
            <p className="text-[10px] text-gray-400 mb-0.5">총 소요시간</p>
            <p className="text-[15px] font-bold text-gray-900">
              {totalH > 0 ? `${totalH}시간 ` : ''}{totalM > 0 ? `${totalM}분` : totalH === 0 ? '—' : ''}
            </p>
          </div>
          {overTime && (
            <span className="text-[11px] text-amber-600 bg-amber-50 px-2.5 py-1 rounded-full font-medium">
              ⚠️ 하루 일정 초과
            </span>
          )}
        </div>

        {editMode && (
          <div className="bg-blue-50 rounded-xl px-3.5 py-2.5 flex items-center gap-2">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="9" stroke="#3b82f6" strokeWidth="1.8"/>
              <path d="M12 8v4M12 16h.01" stroke="#3b82f6" strokeWidth="1.8" strokeLinecap="round"/>
            </svg>
            <p className="text-[12px] text-blue-600">장소를 삭제하거나 순서를 바꿀 수 있어요</p>
          </div>
        )}

        {places.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <span className="text-[40px]">🗺️</span>
            <p className="text-[14px] font-semibold text-gray-400">편집할 일정이 없어요</p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {places.map((place, i) => (
              <div key={place.id} className="bg-white rounded-2xl shadow-sm overflow-hidden">
                <div className="flex items-center gap-2.5 px-3 py-3">
                  {editMode && (
                    <div className="flex flex-col items-center gap-[3px] px-0.5 cursor-grab shrink-0">
                      {[0,1,2].map((row) => (
                        <div key={row} className="flex gap-[3px]">
                          <div className="w-1 h-1 rounded-full bg-gray-300" />
                          <div className="w-1 h-1 rounded-full bg-gray-300" />
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
                    <span className="text-white text-[9px] font-bold">{i + 1}</span>
                  </div>

                  {place.image ? (
                    <img src={place.image} alt={place.name} className="w-12 h-12 rounded-xl object-cover shrink-0" />
                  ) : (
                    <div className="w-12 h-12 rounded-xl bg-[#F1F5F9] flex items-center justify-center shrink-0">
                      <span className="text-[20px]">{place.role === 'meal' ? '🍽️' : place.role === 'cafe' ? '☕' : '📍'}</span>
                    </div>
                  )}

                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] font-bold text-gray-900 truncate">{place.name}</p>
                    <p className="text-[11px] text-gray-400">{ROLE_LABEL[place.role] || place.role} · {place.duration}</p>
                    <p className="text-[10px] text-blue-500 font-medium mt-0.5">{place.time}</p>
                  </div>

                  {editMode && (
                    <div className="flex items-center gap-1 shrink-0">
                      <div className="flex flex-col">
                        <button onClick={() => moveUp(i)} disabled={i === 0} className="p-1 disabled:opacity-20">
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                            <path d="M18 15l-6-6-6 6" stroke="#6b7280" strokeWidth="2" strokeLinecap="round"/>
                          </svg>
                        </button>
                        <button onClick={() => moveDown(i)} disabled={i === places.length - 1} className="p-1 disabled:opacity-20">
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                            <path d="M6 9l6 6 6-6" stroke="#6b7280" strokeWidth="2" strokeLinecap="round"/>
                          </svg>
                        </button>
                      </div>
                      <button
                        onClick={() => handleDelete(place.id)}
                        className="p-1.5 rounded-full text-gray-300 active:text-red-400 transition-colors"
                      >
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                          <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                        </svg>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 하단 버튼 */}
      <div className="absolute bottom-16 left-0 right-0 px-4 pb-2 flex flex-col gap-2">
        <button
          onClick={() => { setEditMode(false); onDone?.(); }}
          className="w-full bg-blue-600 text-white font-bold text-[15px] py-3.5 rounded-2xl"
        >
          {editMode ? '편집 완료' : '저장하고 나가기'}
        </button>
      </div>
    </div>
  );
}
