import { useEffect, useMemo, useState } from 'react';

const RADIUS_OPTIONS = [
  { label: '500m', value: 500 },
  { label: '1km', value: 1000 },
  { label: '3km', value: 3000 },
];

const DEFAULT_SEARCH = '성수';

function SearchIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <circle cx="11" cy="11" r="7" stroke="#2563EB" strokeWidth="2" />
      <path d="M16.5 16.5L21 21" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function PinIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M12 21s7-5.4 7-12a7 7 0 10-14 0c0 6.6 7 12 7 12z" fill="#DBEAFE" stroke="#2563EB" strokeWidth="1.7" />
      <circle cx="12" cy="9" r="2.4" fill="#2563EB" />
    </svg>
  );
}

function PlaceholderImage({ category }) {
  const cafe = /카페/.test(category || '');
  return (
    <div style={{
      width: 78,
      height: 78,
      borderRadius: 18,
      flexShrink: 0,
      background: cafe
        ? 'radial-gradient(circle at 25% 18%, rgba(255,255,255,0.88), transparent 32%), linear-gradient(135deg, #E0F2FE 0%, #F8E7D4 55%, #F8FAFC 100%)'
        : 'radial-gradient(circle at 25% 18%, rgba(255,255,255,0.9), transparent 30%), linear-gradient(135deg, #DBEAFE 0%, #DCFCE7 55%, #F8FAFC 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#2563EB',
      fontSize: 12,
      fontWeight: 900,
      border: '1px solid rgba(226,232,240,0.9)',
    }}>
      {cafe ? 'CAFE' : 'PLACE'}
    </div>
  );
}

function PlaceCard({ place }) {
  const distance = place.distance_m == null
    ? ''
    : place.distance_m >= 1000
      ? `${(place.distance_m / 1000).toFixed(1)}km`
      : `${place.distance_m}m`;

  return (
    <article style={{
      display: 'flex',
      gap: 12,
      padding: 12,
      border: '1px solid #E5E7EB',
      borderRadius: 20,
      background: '#FFFFFF',
      boxShadow: '0 6px 16px rgba(15,23,42,0.05)',
    }}>
      {place.image_url ? (
        <img
          src={place.image_url}
          alt=""
          style={{ width: 78, height: 78, borderRadius: 18, objectFit: 'cover', flexShrink: 0, background: '#F1F5F9' }}
        />
      ) : (
        <PlaceholderImage category={place.category} />
      )}
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
          <span style={{ fontSize: 12, fontWeight: 800, color: '#2563EB' }}>{place.category || '장소'}</span>
          {distance && <span style={{ fontSize: 12, color: '#94A3B8' }}>· {distance}</span>}
        </div>
        <h3 style={{ margin: 0, fontSize: 16, lineHeight: 1.25, fontWeight: 900, color: '#111827', wordBreak: 'keep-all' }}>
          {place.name}
        </h3>
        <p style={{ margin: '6px 0 0', fontSize: 12, color: '#64748B', lineHeight: 1.35 }}>
          {[place.region_1, place.region_2].filter(Boolean).join(' · ')}
        </p>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
          {place.rating != null && (
            <span style={metaPillStyle}>평점 {Number(place.rating).toFixed(1)}</span>
          )}
          {place.review_count != null && Number(place.review_count) > 0 && (
            <span style={metaPillStyle}>리뷰 {Number(place.review_count).toLocaleString()}</span>
          )}
          <span style={{
            ...metaPillStyle,
            color: place.operation_status === 'open' ? '#047857' : '#64748B',
            background: place.operation_status === 'open' ? '#ECFDF5' : '#F8FAFC',
          }}>
            {place.operation_label || '운영 정보 확인 필요'}
          </span>
        </div>
      </div>
    </article>
  );
}

const metaPillStyle = {
  display: 'inline-flex',
  alignItems: 'center',
  minHeight: 24,
  padding: '0 8px',
  borderRadius: 999,
  background: '#F8FAFC',
  color: '#475569',
  fontSize: 11,
  fontWeight: 800,
};

export default function ExploreNearbyScreen({ onCreateCourse, onCreateStayCourse }) {
  const [query, setQuery] = useState(DEFAULT_SEARCH);
  const [radius, setRadius] = useState(1000);
  const [destinations, setDestinations] = useState([]);
  const [selectedDestination, setSelectedDestination] = useState(null);
  const [places, setPlaces] = useState([]);
  const [loadingDestinations, setLoadingDestinations] = useState(false);
  const [loadingNearby, setLoadingNearby] = useState(false);
  const [error, setError] = useState('');
  const [stayPromptOpen, setStayPromptOpen] = useState(false);

  const selectedLabel = useMemo(() => (
    selectedDestination
      ? `${selectedDestination.name} 주변`
      : '목적지를 검색해 주세요'
  ), [selectedDestination]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const q = query.trim();
      if (q.length < 2) {
        setDestinations([]);
        return;
      }
      setLoadingDestinations(true);
      setError('');
      fetch(`/api/explore/destinations?query=${encodeURIComponent(q)}&limit=8`)
        .then((res) => {
          if (!res.ok) throw new Error('목적지 검색 실패');
          return res.json();
        })
        .then((data) => {
          const list = data.destinations || [];
          setDestinations(list);
          if (!selectedDestination && list.length > 0) {
            setSelectedDestination(list[0]);
          }
        })
        .catch((err) => setError(err.message || '목적지를 찾지 못했어요.'))
        .finally(() => setLoadingDestinations(false));
    }, 260);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    if (!selectedDestination?.latitude || !selectedDestination?.longitude) return;
    setLoadingNearby(true);
    setError('');
    const params = new URLSearchParams({
      lat: String(selectedDestination.latitude),
      lon: String(selectedDestination.longitude),
      radius_m: String(radius),
      limit: '30',
    });
    fetch(`/api/explore/nearby?${params.toString()}`)
      .then((res) => {
        if (!res.ok) throw new Error('주변 장소 조회 실패');
        return res.json();
      })
      .then((data) => setPlaces(data.places || []))
      .catch((err) => setError(err.message || '주변 장소를 불러오지 못했어요.'))
      .finally(() => setLoadingNearby(false));
  }, [selectedDestination, radius]);

  const handleCourseChoice = (isStay) => {
    if (!selectedDestination) return;
    setStayPromptOpen(false);
    const payload = {
      region: selectedDestination.region_1,
      displayRegion: selectedDestination.region_1,
      region_travel_type: 'urban',
      start_lat: selectedDestination.latitude,
      start_lon: selectedDestination.longitude,
      start_anchor: selectedDestination.name,
      start_anchor_label: selectedDestination.name,
      selectedAnchor: selectedDestination.name,
      selected_anchor_vibe: selectedDestination.name,
      departure_anchor: selectedDestination.name,
      zone_id: `explore_${selectedDestination.place_id}`,
      selected_time_band: 'daytime',
      mapped_departure_time: '오늘 12:00',
      departure_time: '오늘 12:00',
      departure_time_user_selected: false,
      _homeAnchor: {
        zone_id: `explore_${selectedDestination.place_id}`,
        name: selectedDestination.name,
        center_lat: selectedDestination.latitude,
        center_lon: selectedDestination.longitude,
      },
    };
    if (isStay) {
      onCreateStayCourse({ ...payload, stay_base: true, trip_days: 2, template: 'full' });
      return;
    }
    onCreateCourse(payload);
  };

  return (
    <div style={{ minHeight: '100dvh', background: '#F8FAFC', padding: '22px 18px 120px' }}>
      <header style={{ marginBottom: 18 }}>
        <p style={{ margin: 0, fontSize: 13, fontWeight: 800, color: '#2563EB' }}>목적지 주변 둘러보기</p>
        <h1 style={{ margin: '6px 0 0', fontSize: 25, lineHeight: 1.2, fontWeight: 950, color: '#0F172A' }}>
          머무는 곳 근처에서<br />요즘 많이 찾는 장소
        </h1>
      </header>

      <section style={{ background: '#FFFFFF', borderRadius: 22, padding: 14, border: '1px solid #E5E7EB', boxShadow: '0 8px 22px rgba(15,23,42,0.06)' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 10, height: 48, borderRadius: 16, background: '#F8FAFC', padding: '0 12px', border: '1px solid #E2E8F0' }}>
          <SearchIcon />
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setSelectedDestination(null);
            }}
            placeholder="목적지, 숙소 근처, 역 이름 검색"
            style={{ flex: 1, border: 'none', outline: 'none', background: 'transparent', fontSize: 15, fontWeight: 700, color: '#111827', minWidth: 0 }}
          />
        </label>

        <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingTop: 12 }}>
          {loadingDestinations && <span style={{ fontSize: 13, color: '#64748B' }}>검색 중...</span>}
          {!loadingDestinations && destinations.map((item) => {
            const active = selectedDestination?.place_id === item.place_id;
            return (
              <button
                key={item.place_id}
                type="button"
                onClick={() => setSelectedDestination(item)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  flexShrink: 0,
                  height: 38,
                  padding: '0 12px',
                  borderRadius: 999,
                  border: active ? '1.5px solid #2563EB' : '1px solid #E2E8F0',
                  background: active ? '#EFF6FF' : '#FFFFFF',
                  color: active ? '#1D4ED8' : '#475569',
                  fontSize: 13,
                  fontWeight: 900,
                }}
              >
                <PinIcon />
                {item.name}
              </button>
            );
          })}
        </div>
      </section>

      <section style={{ marginTop: 14, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ minWidth: 0 }}>
          <p style={{ margin: 0, fontSize: 13, color: '#64748B', fontWeight: 800 }}>현재 기준</p>
          <h2 style={{ margin: '3px 0 0', fontSize: 18, color: '#111827', fontWeight: 950, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {selectedLabel}
          </h2>
        </div>
        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
          {RADIUS_OPTIONS.map((option) => {
            const active = radius === option.value;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => setRadius(option.value)}
                style={{
                  height: 34,
                  padding: '0 10px',
                  borderRadius: 999,
                  border: active ? '1.5px solid #2563EB' : '1px solid #E2E8F0',
                  background: active ? '#2563EB' : '#FFFFFF',
                  color: active ? '#FFFFFF' : '#475569',
                  fontSize: 12,
                  fontWeight: 900,
                }}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </section>

      {error && (
        <p style={{ margin: '14px 2px 0', fontSize: 13, color: '#DC2626', fontWeight: 800 }}>{error}</p>
      )}

      <section style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {loadingNearby && (
          [0, 1, 2].map((idx) => (
            <div key={idx} style={{ height: 104, borderRadius: 20, background: 'linear-gradient(90deg, #F1F5F9, #FFFFFF, #F1F5F9)', border: '1px solid #E5E7EB' }} />
          ))
        )}
        {!loadingNearby && places.map((place) => (
          <PlaceCard key={place.place_id} place={place} />
        ))}
        {!loadingNearby && selectedDestination && places.length === 0 && (
          <div style={{ padding: 22, borderRadius: 20, background: '#FFFFFF', border: '1px solid #E5E7EB', color: '#64748B', fontSize: 14, fontWeight: 800, textAlign: 'center' }}>
            선택한 반경 안에서 표시할 장소가 아직 없어요.
          </div>
        )}
      </section>

      <div style={{ position: 'fixed', left: 18, right: 18, bottom: 'calc(96px + env(safe-area-inset-bottom, 0px))', zIndex: 30 }}>
        <button
          type="button"
          disabled={!selectedDestination}
          onClick={() => setStayPromptOpen(true)}
          style={{
            width: '100%',
            height: 56,
            border: 'none',
            borderRadius: 999,
            background: selectedDestination ? '#2563EB' : '#CBD5E1',
            color: '#FFFFFF',
            fontSize: 16,
            fontWeight: 950,
            boxShadow: selectedDestination ? '0 12px 26px rgba(37,99,235,0.28)' : 'none',
          }}
        >
          이 주변으로 여행 코스 만들기
        </button>
      </div>

      {stayPromptOpen && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(15,23,42,0.34)', display: 'flex', alignItems: 'flex-end', padding: 16 }}>
          <div style={{ width: '100%', borderRadius: 26, background: '#FFFFFF', padding: 20, boxShadow: '0 -12px 34px rgba(15,23,42,0.2)' }}>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 950, color: '#111827' }}>숙박 예정이신가요?</h2>
            <p style={{ margin: '8px 0 18px', fontSize: 14, lineHeight: 1.5, color: '#64748B', fontWeight: 700 }}>
              아니오를 선택하면 기존 당일 여행 추천으로 이어집니다. 예를 선택하면 숙박지 기준 2일 이상 코스 흐름으로 시작합니다.
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <button type="button" onClick={() => handleCourseChoice(false)} style={modalButtonStyle('#FFFFFF', '#2563EB', '#BFDBFE')}>
                아니오
              </button>
              <button type="button" onClick={() => handleCourseChoice(true)} style={modalButtonStyle('#2563EB', '#FFFFFF', '#2563EB')}>
                예
              </button>
            </div>
            <button type="button" onClick={() => setStayPromptOpen(false)} style={{ marginTop: 10, width: '100%', height: 44, border: 'none', background: 'transparent', color: '#64748B', fontSize: 14, fontWeight: 900 }}>
              닫기
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function modalButtonStyle(background, color, borderColor) {
  return {
    height: 52,
    borderRadius: 16,
    border: `1px solid ${borderColor}`,
    background,
    color,
    fontSize: 15,
    fontWeight: 950,
  };
}
