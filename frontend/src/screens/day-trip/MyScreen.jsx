import { useState } from 'react';
import {
  deleteSavedCourse,
  getRegenerateParams,
  getSavedCourse,
  loadSavedCourses,
} from '../../utils/savedCourses';
import { getDisplayPlaceDescription } from '../../utils/placeDescription';

/* ─── SVG 아이콘 ──────────────────────────────────── */
const ChevronRight = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-[#CBD5E1]">
    <path d="M9 18l6-6-6-6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const isSafeExternalUrl = (url) => {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:';
  } catch {
    return false;
  }
};

/* ─── 메인 컴포넌트 ───────────────────────────────── */
export default function MyScreen({ onGoHome, onRegenerateCourse }) {
  const [initialSavedState] = useState(() => loadSavedCourses());
  const [savedCourses, setSavedCourses] = useState(initialSavedState.courses);
  const [recentCourses] = useState([]);
  const [storageError, setStorageError] = useState(
    initialSavedState.ok ? null : initialSavedState.error
  );
  const [statusMessage, setStatusMessage] = useState(null);
  const [selectedSavedCourse, setSelectedSavedCourse] = useState(null);
  const [deleteTargetCourse, setDeleteTargetCourse] = useState(null);
  const sajuServiceUrl = import.meta.env.VITE_SAJU_SERVICE_URL;
  const showSajuLink =
    import.meta.env.VITE_SHOW_SAJU_LINK === 'true' &&
    typeof sajuServiceUrl === 'string' &&
    isSafeExternalUrl(sajuServiceUrl);

  const handleDeleteSavedCourse = (courseId) => {
    const result = deleteSavedCourse(courseId);
    if (!result.ok) {
      setStorageError(result.error);
      return;
    }
    setSavedCourses(result.courses);
    setStorageError(null);
    setStatusMessage('저장한 코스를 삭제했어요.');
    if (selectedSavedCourse?.course_id === courseId) {
      setSelectedSavedCourse(null);
    }
    setDeleteTargetCourse(null);
  };

  const requestDeleteSavedCourse = (course) => {
    setDeleteTargetCourse(course);
  };

  const handleOpenSavedCourse = (courseId) => {
    const result = getSavedCourse(courseId);
    if (!result.ok) {
      setStorageError(result.error);
      return;
    }
    if (!result.course) {
      setSelectedSavedCourse(null);
      setStorageError('COURSE_NOT_FOUND');
      setStatusMessage('저장한 코스를 찾을 수 없어요.');
      return;
    }
    setStorageError(null);
    setSelectedSavedCourse(result.course);
  };

  const handleRegenerateSavedCourse = (course) => {
    const result = getRegenerateParams(course);
    if (!result.ok) {
      setStorageError(result.warnings?.[0] || 'REGENERATE_UNAVAILABLE');
      setStatusMessage('이 저장 코스는 다시 만들기에 필요한 정보가 부족해요.');
      return;
    }
    onRegenerateCourse?.(result.params);
  };

  return (
    <div className="bg-white min-h-[100dvh] flex flex-col relative">

      {selectedSavedCourse && (
        <SavedCourseDetail
          course={selectedSavedCourse}
          onBack={() => setSelectedSavedCourse(null)}
          onDelete={() => requestDeleteSavedCourse(selectedSavedCourse)}
          onRegenerate={() => handleRegenerateSavedCourse(selectedSavedCourse)}
        />
      )}

      {deleteTargetCourse && (
        <DeleteConfirmSheet
          course={deleteTargetCourse}
          onCancel={() => setDeleteTargetCourse(null)}
          onConfirm={() => handleDeleteSavedCourse(deleteTargetCourse.course_id)}
        />
      )}

      {/* ─── 헤더 영역 ─── */}
      <div className={`px-5 pt-8 pb-6 bg-white sticky top-0 z-20 ${selectedSavedCourse ? 'hidden' : ''}`}>
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
          <div className="w-10" aria-hidden="true" />
        </div>
      </div>

      {/* ─── 본문 영역 ─── */}
      <div className={`flex-1 px-5 pb-[200px] ${selectedSavedCourse ? 'hidden' : ''}`}>

        {statusMessage && (
          <div className="mt-4 rounded-2xl border border-[#BBF7D0] bg-[#F0FDF4] px-4 py-3 text-[13px] font-bold text-[#15803D]">
            {statusMessage}
          </div>
        )}

        {showSajuLink && (
          <div className="mt-4 mb-8">
            <a
              href={sajuServiceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between rounded-[22px] border border-[#E0E7FF] bg-gradient-to-br from-[#EEF2FF] to-white px-5 py-4 shadow-[0_4px_18px_rgba(79,70,229,0.08)] active:scale-[0.98] transition-transform"
              aria-label="사주/MBTI 서비스 새 탭으로 열기"
            >
              <div className="flex flex-col gap-1">
                <span className="text-[15px] font-extrabold text-[#312E81]">사주/MBTI 보러가기</span>
                <span className="text-[12px] font-semibold text-[#6366F1]">여행 성향도 가볍게 확인해 보세요</span>
              </div>
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-[20px] shadow-sm">
                ↗
              </span>
            </a>
          </div>
        )}

        <div className="mt-4 mb-8">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-[17px] font-extrabold text-[#111827]">저장한 코스</h3>
          </div>
          {storageError && (
            <div className="mb-4 rounded-2xl border border-[#FDE68A] bg-[#FFFBEB] px-4 py-3 text-[13px] font-semibold text-[#92400E]">
              {getStorageErrorMessage(storageError)}
            </div>
          )}
          {savedCourses.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 px-5 bg-[#F8FAFC] rounded-[24px] gap-2 text-center border border-[#F1F5F9]">
              <div className="mb-1 flex h-14 w-14 items-center justify-center rounded-full bg-white text-[30px] shadow-sm">🗺️</div>
              <p className="text-[16px] font-extrabold text-[#111827]">저장한 코스가 없습니다</p>
              <p className="max-w-[240px] text-[13px] leading-relaxed text-[#94A3B8]">
                마음에 드는 여행 코스를 저장하면 이곳에서 다시 볼 수 있어요.
              </p>
              <button
                type="button"
                onClick={onGoHome}
                className="mt-4 rounded-full bg-[#2563EB] px-5 py-2.5 text-[13px] font-bold text-white active:scale-[0.98]"
              >
                코스 만들러 가기
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-3.5">
              {savedCourses.map((course) => (
                <div
                  key={course.course_id}
                  role="button"
                  tabIndex={0}
                  onClick={() => handleOpenSavedCourse(course.course_id)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      handleOpenSavedCourse(course.course_id);
                    }
                  }}
                  className="w-full bg-white rounded-[22px] border border-[#F1F5F9] shadow-[0_4px_16px_rgba(15,23,42,0.04)] p-4 flex items-center gap-4 text-left active:scale-[0.99] transition-transform"
                >
                  {course.places?.[0]?.image
                    ? <img src={course.places[0].image} alt="" className="w-16 h-16 rounded-2xl object-cover shrink-0" />
                    : <div className="w-16 h-16 rounded-2xl bg-[#EFF6FF] shrink-0 flex items-center justify-center text-[26px]">🗺️</div>
                  }
                  <div className="flex-1 min-w-0">
                    <div className="mb-1 flex items-center gap-2">
                      <p className="truncate text-[16px] font-extrabold text-[#1F2937]">{course.region}</p>
                      {course.place_count ? (
                        <span className="shrink-0 rounded-full bg-[#EFF6FF] px-2 py-0.5 text-[10px] font-extrabold text-[#2563EB]">
                          {course.place_count}곳
                        </span>
                      ) : null}
                    </div>
                    <p className="text-[12px] text-[#64748B] font-semibold truncate mb-1">
                      {course.summary || `${course.place_count || 0}곳 코스`}
                    </p>
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] font-medium text-[#94A3B8]">
                      <span>{formatSavedAt(course)}</span>
                      {course.total_travel_min != null && <span>이동 {course.total_travel_min}분</span>}
                    </div>
                    <p className="mt-1.5 text-[11px] font-bold text-[#2563EB]">탭해서 다시 보기</p>
                  </div>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      requestDeleteSavedCourse(course);
                    }}
                    className="rounded-full border border-[#FEE2E2] px-3 py-2 text-[12px] font-bold text-[#EF4444] active:bg-red-50"
                    aria-label={`${course.region} 저장 코스 삭제`}
                  >
                    삭제
                  </button>
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
      <div className={`fixed left-0 right-0 px-5 z-20 ${selectedSavedCourse ? 'hidden' : ''}`} style={{ bottom: 'calc(104px + env(safe-area-inset-bottom, 0px))' }}>
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

function SavedCourseDetail({ course, onBack, onDelete, onRegenerate }) {
  const savedAt = new Date(course.updated_at || course.created_at).toLocaleString('ko-KR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div className="absolute inset-0 z-30 bg-[#F8FAFC] overflow-y-auto">
      <div className="sticky top-0 z-20 bg-white px-5 pt-7 pb-4 border-b border-[#F1F5F9]">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={onBack}
            className="rounded-full border border-[#E2E8F0] bg-white px-4 py-2 text-[13px] font-bold text-[#475569] active:bg-gray-50"
          >
            목록
          </button>
          <button
            type="button"
            onClick={onDelete}
            className="rounded-full border border-[#FEE2E2] bg-white px-4 py-2 text-[13px] font-bold text-[#EF4444] active:bg-red-50"
          >
            삭제
          </button>
        </div>
      </div>

      <div className="px-5 pt-5 pb-[calc(180px+env(safe-area-inset-bottom,0px))]">
        <div className="mb-5 rounded-[26px] bg-white p-5 shadow-sm border border-[#F1F5F9]">
          <p className="text-[13px] font-bold text-[#2563EB] mb-1">저장한 코스</p>
          <h2 className="text-[22px] font-extrabold text-[#111827] mb-2">{course.region}</h2>
          <p className="text-[13px] font-semibold text-[#64748B] mb-3">{savedAt}</p>
          {course.summary && (
            <p className="text-[14px] leading-relaxed text-[#475569] whitespace-pre-line break-words">{course.summary}</p>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <span className="rounded-full bg-[#EFF6FF] px-3 py-1.5 text-[12px] font-bold text-[#2563EB]">
              {course.place_count || course.places.length}곳
            </span>
            {course.total_travel_min != null && (
              <span className="rounded-full bg-[#F8FAFC] px-3 py-1.5 text-[12px] font-bold text-[#64748B]">
                이동 {course.total_travel_min}분
              </span>
            )}
            {course.total_duration_min != null && (
              <span className="rounded-full bg-[#F8FAFC] px-3 py-1.5 text-[12px] font-bold text-[#64748B]">
                총 {Math.floor(course.total_duration_min / 60)}시간{course.total_duration_min % 60 ? ` ${course.total_duration_min % 60}분` : ''}
              </span>
            )}
          </div>
          <div className="mt-5 rounded-[20px] bg-[#F8FAFC] p-4">
            <p className="mb-3 text-[13px] font-bold leading-relaxed text-[#475569]">
              저장했던 지역과 조건을 바탕으로 새 코스를 다시 추천받을 수 있어요.
            </p>
            <button
              type="button"
              onClick={onRegenerate}
              className="h-12 w-full rounded-full bg-[#2563EB] text-[14px] font-extrabold text-white shadow-[0_8px_18px_rgba(37,99,235,0.25)] active:scale-[0.98]"
            >
              비슷한 코스 다시 만들기
            </button>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={onBack}
              className="h-12 rounded-full border border-[#BFDBFE] bg-white text-[13px] font-extrabold text-[#2563EB] active:bg-blue-50"
            >
              저장 목록
            </button>
            <button
              type="button"
              onClick={onDelete}
              className="h-12 rounded-full border border-[#FEE2E2] bg-white text-[13px] font-extrabold text-[#EF4444] active:bg-red-50"
            >
              삭제
            </button>
          </div>
        </div>

        {(course.option_notice || course.missing_slot_reason) && (
          <div className="mb-5 rounded-[20px] border border-[#BFDBFE] bg-[#EFF6FF] px-4 py-3 text-[13px] font-semibold leading-relaxed text-[#1D4ED8]">
            {course.option_notice || course.missing_slot_reason}
          </div>
        )}

        <div className="space-y-4">
          <h3 className="px-1 pb-1 text-[16px] font-extrabold text-[#111827]">장소 목록</h3>
          {course.places.map((place, index) => (
            <div key={`${place.place_id || place.name}-${index}`} className="rounded-[22px] border border-[#F1F5F9] bg-white p-4 shadow-sm">
              <div className="flex gap-4">
                {place.image ? (
                  <img src={place.image} alt={place.name} className="h-20 w-20 shrink-0 rounded-2xl object-cover" />
                ) : (
                  <div className="h-20 w-20 shrink-0 rounded-2xl bg-[#F1F5F9]" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#EFF6FF] text-[12px] font-extrabold text-[#2563EB]">
                      {index + 1}
                    </span>
                    {place.time && <span className="text-[12px] font-bold text-[#94A3B8]">{place.time}</span>}
                  </div>
                  <h3 className="mb-1 truncate text-[16px] font-extrabold text-[#111827]">{place.name}</h3>
                  <p className="text-[12px] font-semibold text-[#64748B]">
                    {place.role || 'place'}{place.duration ? ` · ${place.duration}` : ''}
                  </p>
                </div>
              </div>
              <p className="mt-3 text-[13px] leading-relaxed text-[#475569] whitespace-pre-line break-words">
                {getDisplayPlaceDescription(place, {
                  region: course.region,
                  index,
                })}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function DeleteConfirmSheet({ course, onCancel, onConfirm }) {
  return (
    <>
      <div className="fixed inset-0 z-[90] bg-black/35" onClick={onCancel} />
      <div
        className="fixed left-0 right-0 z-[91] rounded-t-[28px] bg-white px-5 pt-5 shadow-[0_-16px_40px_rgba(15,23,42,0.18)]"
        style={{ bottom: 0, paddingBottom: 'calc(24px + env(safe-area-inset-bottom, 0px))' }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-saved-course-title"
      >
        <div className="mx-auto mb-4 h-1.5 w-10 rounded-full bg-[#E2E8F0]" />
        <h3 id="delete-saved-course-title" className="mb-2 text-[18px] font-extrabold text-[#111827]">
          저장한 코스를 삭제할까요?
        </h3>
        <p className="mb-5 text-[13px] font-semibold leading-relaxed text-[#64748B]">
          {course?.region || '저장한 코스'} 코스가 이 기기에서 삭제됩니다. 삭제 후에는 저장 목록에서 다시 열 수 없어요.
        </p>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="h-12 rounded-full border border-[#E2E8F0] bg-white text-[14px] font-extrabold text-[#475569] active:bg-gray-50"
          >
            취소
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="h-12 rounded-full bg-[#EF4444] text-[14px] font-extrabold text-white active:scale-[0.98]"
          >
            삭제
          </button>
        </div>
      </div>
    </>
  );
}

function getStorageErrorMessage(error) {
  if (error === 'COURSE_NOT_FOUND') return '저장한 코스를 찾을 수 없습니다.';
  if (error === 'INVALID_SAVED_COURSE') return '저장 데이터가 손상되어 열 수 없습니다.';
  if (error === 'REGION_MISSING') return '다시 만들기에 필요한 지역 정보가 없습니다.';
  return '이 브라우저에서는 저장 목록을 불러올 수 없습니다.';
}

function formatSavedAt(course) {
  return new Date(course.updated_at || course.created_at).toLocaleString('ko-KR', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
