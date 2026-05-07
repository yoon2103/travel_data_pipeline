import { useState, useEffect } from 'react';
import { MOOD_TO_THEMES } from '../../data/dayTripDummyData';

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
    lat:      c.latitude ?? null,
    lon:      c.longitude ?? null,
  };
}

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

/* ─── 메인 컴포넌트 ──────────────────────────────────── */
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

  // ── API 호출 ──
  useEffect(() => {
    if (!params) return;
    const themes = MOOD_TO_THEMES[params.mood] ?? [];

    const DENSITY_TO_TEMPLATE = { '여유롭게': 'light', '적당히': 'standard', '알차게': 'full' };
    const template = DENSITY_TO_TEMPLATE[params.density] ?? params.template ?? 'standard';

    const WALK_TO_RADIUS = { '적게': 5, '보통': 10, '조금 멀어도 좋아요': 18 };
    const walk_max_radius = WALK_TO_RADIUS[params.walk] ?? null;

    const payload = {
      region:              params.region,
      departure_time:      params.departure_time,
      start_anchor:        params.start_anchor ?? null,
      start_lat:           params.start_lat ?? null,
      start_lon:           params.start_lon ?? null,
      themes,
      template,
      region_travel_type:  params.region_travel_type ?? 'urban',
      zone_id:             params.zone_id ?? null,
      walk_max_radius,
    };
    console.log('[CourseGenerate] request payload:', payload);

    fetch('/api/course/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(res => {
        if (!res.ok) throw new Error(`서버 오류 (${res.status})`);
        return res.json();
      })
      .then(data => {
        console.log('[CourseGenerate] response:', data);
        if (data.error) throw new Error(data.error);
        const normalized = (data.places || []).map(normalizePlace);
        console.log('[CourseGenerate] normalized places:', normalized);
        setCourseId(data.course_id ?? null);
        setCourseDesc(data.description ?? null);
        setMissingSlotReason(data.missing_slot_reason ?? null);
        setOptionNotice(data.option_notice ?? null);
        setTotalDuration(data.total_duration_min ?? null);
        setTotalTravel(data.total_travel_min ?? null);
        setRegionStatus(data.region_status ?? null);
        setPlaces(normalized);
        setExpandedIds(normalized.length > 0 ? [normalized[0].id] : []);
        setLoading(false);
      })
      .catch(err => {
        setApiError(err.message || '코스를 불러오지 못했습니다.');
        setLoading(false);
      });
  }, [params]);

  const isEdit = mode === 'edit';
  const addBlockedReason = (() => {
    if (places.length < 5) return '장소가 5개 미만인 코스는 장소를 추가하지 않습니다.';
    if (regionStatus === 'LIMITED') return '데이터가 제한된 지역은 장소 추가를 지원하지 않습니다.';
    if (regionStatus === 'BLOCKED') return '현재 서비스 제한 지역은 장소 추가를 지원하지 않습니다.';
    return null;
  })();
  const canAddPlace = !hasAddedPlace && !addBlockedReason;

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
      alert(addBlockedReason);
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
      .then(res => { if (!res.ok) throw new Error(`교체 실패 (${res.status})`); return res.json(); })
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
      alert('저장할 코스 정보가 없습니다.');
      return;
    }
    setSaving(true);
    fetch(`/api/course/${courseId}/save`, { method: 'POST' })
      .then(res => { if (!res.ok) throw new Error(); onSave?.(); })
      .catch(() => alert('코스 저장에 실패했어요. 다시 시도해주세요.'))
      .finally(() => setSaving(false));
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
          throw new Error(data.detail || `재계산 실패 (${res.status})`);
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
        alert(err.message || '경로 재계산에 실패했어요.');
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
        <div className="flex items-center justify-between px-4 py-4">
          <button onClick={onBack} className="p-1 -ml-1"><BackIcon /></button>
          <h2 className="text-[17px] font-bold text-[#111827]">추천 코스</h2>
          <div className="w-8" />
        </div>
        <div className="flex-1 flex flex-col items-center justify-center gap-4 pb-20">
          <div className="w-10 h-10 border-4 border-[#2563EB] border-t-transparent rounded-full animate-spin" />
          <p className="text-[15px] font-semibold text-[#475569]">코스를 생성하고 있어요...</p>
        </div>
      </div>
    );
  }

  /* ── 에러 화면 ── */
  if (apiError) {
    return (
      <div className="bg-[#F8FAFC] min-h-[100dvh] flex flex-col">
        <div className="flex items-center justify-between px-4 py-4">
          <button onClick={onBack} className="p-1 -ml-1"><BackIcon /></button>
          <h2 className="text-[17px] font-bold text-[#111827]">추천 코스</h2>
          <div className="w-8" />
        </div>
        <div className="flex-1 flex flex-col items-center justify-center gap-4 px-6 pb-40">
          <div className="w-12 h-12 bg-[#FEF2F2] rounded-full flex items-center justify-center">
            <WarnIcon />
          </div>
          <p className="text-[16px] font-bold text-[#111827] text-center">코스를 불러오지 못했어요</p>
          <p className="text-[13px] text-[#64748B] text-center">{apiError}</p>
          <button
            onClick={onBack}
            className="mt-2 px-6 py-3 bg-[#2563EB] text-white text-[14px] font-bold rounded-full"
          >
            다시 시도하기
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-[#F8FAFC] min-h-[100dvh] flex flex-col relative overflow-x-hidden">

      {/* 헤더 */}
      <div className="bg-[#F8FAFC] sticky top-0 z-20">
        <div className="flex items-center justify-between px-4 py-4">
          <button onClick={onBack} className="p-1 -ml-1"><BackIcon /></button>
          <h2 className="text-[17px] font-bold text-[#111827]">추천 코스</h2>
          <button className="p-1"><ShareIcon /></button>
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

      <div className="px-5 pt-2 pb-[240px]">
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
        <div className="flex flex-col">
          {places.map((place, index) => {
            const isExpanded = expandedIds.includes(place.id);
            const isDragging = draggingIndex === index;
            const isDraggable = isEdit && activeDragId === place.id;
            const hasNext = index < places.length - 1;

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
                <div className="flex items-center gap-1.5 mb-1 pl-0.5">
                  <span className="text-[14px] font-extrabold text-[#111827] w-[45px]">{place.time}</span>
                  {place.endTime && (
                    <span className="text-[12px] font-semibold text-[#9CA3AF]">~ {place.endTime}</span>
                  )}
                </div>

                {/* 카드 + 타임라인 축 */}
                <div className="flex items-stretch relative">
                  <div className="w-[45px] shrink-0 flex flex-col items-center relative z-0">
                    <div className="w-[12px] h-[12px] rounded-full border-[3px] border-[#3B82F6] bg-white z-10 mt-[26px]" />
                    {hasNext && <div className="absolute top-[34px] bottom-0 w-[2px] bg-[#3B82F6]" />}
                  </div>

                  <div className="flex-1 pb-3 relative z-10">
                    <div className="bg-white rounded-[20px] border border-[#F1F5F9] shadow-[0_4px_16px_rgba(15,23,42,0.06)] overflow-hidden">

                      {/* 카드 헤더 */}
                      <div className="flex items-center gap-3.5 px-3 py-3">
                        {place.image ? (
                          <img
                            src={place.image}
                            className={`w-[60px] h-[60px] object-cover rounded-[14px] transition-all duration-300 ${isExpanded ? 'opacity-0 w-0 h-0 ml-[-12px]' : 'opacity-100'}`}
                            alt={place.name}
                          />
                        ) : (
                          <div className={`w-[60px] h-[60px] rounded-[14px] bg-[#F1F5F9] flex items-center justify-center shrink-0 transition-all duration-300 ${isExpanded ? 'opacity-0 w-0 h-0 ml-[-12px]' : 'opacity-100'}`}>
                            <span className="text-[22px]">{place.role === 'meal' ? '🍽️' : place.role === 'cafe' ? '☕' : '📍'}</span>
                          </div>
                        )}
                        <div className="flex-1 min-w-0 cursor-pointer py-1" onClick={() => toggleAccordion(place.id)}>
                          <h4 className="text-[16px] font-bold text-[#1F2937] truncate mb-0.5">{place.name}</h4>
                          <p className="text-[13px] text-[#64748B] font-medium truncate">{place.duration}</p>

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
                        <div className="px-4 pb-5 pt-1 border-t border-[#F1F5F9]/60">
                          {place.image && <img src={place.image} className="w-full h-[180px] object-cover rounded-[16px] mb-4 mt-3 shadow-sm" alt={place.name} />}
                          <p className="text-[13px] text-[#475569] leading-relaxed mb-1">{place.description}</p>
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
                      <div className="px-4 py-2 bg-white border border-[#E2E8F0] rounded-full shadow-[0_2px_8px_rgba(0,0,0,0.04)] flex items-center gap-1.5">
                        <CarIcon />
                        <span className="text-[12px] font-bold text-[#475569]">{place.transit}</span>
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
          })}
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
      <div className="fixed bottom-0 left-0 right-0 px-6 pt-16 bg-gradient-to-t from-[#F8FAFC] via-[#F8FAFC]/95 to-transparent z-30 flex flex-col gap-2.5 pointer-events-none" style={{ paddingBottom: 'calc(32px + env(safe-area-inset-bottom, 0px))' }}>
        {mode === 'view' ? (
          <>
            <button onClick={() => onRemakeMood?.()} className="w-full h-[52px] bg-white text-[#3B82F6] font-bold text-[14px] border border-[#E2E8F0] rounded-full shadow-sm active:bg-gray-50 pointer-events-auto flex items-center justify-center gap-2">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              다른 분위기로 다시 만들기
            </button>
            <div className="flex gap-2.5 pointer-events-auto">
              <button
                disabled
                className="flex-1 h-[52px] bg-white text-[#94A3B8] font-bold text-[14px] border border-[#E2E8F0] rounded-full shadow-sm disabled:opacity-70"
              >
                저장 준비중
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
                <span className="text-[13px] font-semibold text-[#92400E]">경로를 먼저 다시 계산해주세요.</span>
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
              경로 다시 계산
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
              완료
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
                  <button onClick={closeSheet} className="p-1 -ml-2"><BackIcon /></button>
                  <h3 className="text-[18px] font-bold text-[#111827]">{sheetData.title}</h3>
                  <button onClick={closeSheet} className="p-1 -mr-2"><CloseIcon /></button>
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
                  <p className="text-center text-[13px] text-[#94A3B8] py-8">추천 후보가 없습니다.</p>
                ) : (
                  candidates.map((c) => (
                    <div key={c.id} className="flex items-center gap-4 p-4 rounded-[20px] border border-[#F1F5F9] bg-white shadow-sm">
                      {c.image
                        ? <img src={c.image} className="w-[72px] h-[72px] object-cover rounded-2xl" alt={c.name} />
                        : <div className="w-[72px] h-[72px] rounded-2xl bg-[#F1F5F9] flex items-center justify-center shrink-0"><span className="text-[28px]">{c.category === 'meal' ? '🍽️' : c.category === 'cafe' ? '☕' : '📍'}</span></div>
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
