import { useState } from 'react';
import MobileShell from './components/common/MobileShell';
import HomeScreen from './screens/day-trip/HomeScreen';
import ConditionScreen from './screens/day-trip/ConditionScreen';
import CourseResultScreen from './screens/day-trip/CourseResultScreen';
import MyScreen from './screens/day-trip/MyScreen';

function DayTripApp({ initialScreen = 'home' }) {
  const [screen, setScreen] = useState(initialScreen);
  const [courseParams, setCourseParams] = useState({
    // HomeScreen이 채움
    region:             null,
    displayRegion:      null,
    departure_time:     null,
    region_travel_type: 'urban',
    start_lat:          null,
    start_lon:          null,
    start_anchor:       null,
    zone_id:            null,
    _homeAnchor:        null,  // HomeScreen 재진입 시 anchor 복원용
    // ConditionScreen이 채움
    mood:     '자연 선택',
    walk:     '보통',
    density:  '적당히',
  });
  const tabMap = { home: 'home', condition: 'home', result: 'home', my: 'my' };

  function handleParamChange(key, val) {
    setCourseParams(prev => ({ ...prev, [key]: val }));
  }

  function handleTabChange(tab) {
    if (tab === 'home') setScreen('home');
    if (tab === 'saved' || tab === 'my') setScreen('my');
  }

  return (
    <MobileShell activeTab={tabMap[screen] || 'home'} onTabChange={handleTabChange}>
      {screen === 'home' && (
        <HomeScreen
          courseParams={courseParams}
          onParamChange={handleParamChange}
          onNext={(homeParams) => {
            setCourseParams(prev => ({ ...prev, ...homeParams }));
            setScreen('condition');
          }}
        />
      )}
      {screen === 'condition' && (
        <ConditionScreen
          onBack={() => setScreen('home')}
          courseParams={courseParams}
          onParamChange={handleParamChange}
          onNext={() => setScreen('result')}
        />
      )}
      {screen === 'result' && (
        <CourseResultScreen
          params={courseParams}
          onBack={() => setScreen('condition')}
          onSave={() => setScreen('my')}
          onRemakeMood={() => setScreen('condition')}
        />
      )}
      {screen === 'my' && <MyScreen onGoHome={() => setScreen('home')} />}
    </MobileShell>
  );
}

function OverviewPage() {
  const screens = [
    { id: 'home', label: '① 홈(시작)', desc: '가볍게 시작' },
    { id: 'condition', label: '② 조건 선택', desc: '기본 + 우선 고려' },
    { id: 'result', label: '③ 추천 코스', desc: '타임라인 중심' },
    { id: 'my', label: '④ 저장/마이', desc: '자연스러운 재방문' },
  ];

  return (
    <div className="min-h-screen bg-gray-100 py-10 px-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-800 mb-1">여행 코스 추천 앱 — UI 검토</h1>
        <p className="text-gray-500 text-sm">5개 화면 나란히 보기 · 각 화면 인터랙션 가능</p>
      </div>
      <div className="flex gap-6 overflow-x-auto pb-6">
        {screens.map((s) => (
          <div key={s.id} className="flex-shrink-0">
            <div className="mb-3">
              <p className="text-[14px] font-bold text-gray-700">{s.label}</p>
              <p className="text-[12px] text-gray-400">{s.desc}</p>
            </div>
            <DayTripApp initialScreen={s.id} />
          </div>
        ))}
      </div>
    </div>
  );
}

function IndividualPage() {
  return (
    <div className="min-h-[100dvh] bg-[#e8eef5] flex items-center justify-center sm:py-10">
      <DayTripApp />
    </div>
  );
}

export default function App() {
  const [mode, setMode] = useState('individual');
  const showScreenReview =
    import.meta.env.DEV || import.meta.env.VITE_SHOW_SCREEN_REVIEW === 'true';
  const activeMode = showScreenReview ? mode : 'individual';

  return (
    <div>
      {showScreenReview && (
        <div className="fixed top-4 right-4 z-50 flex items-center gap-1 bg-white shadow-lg rounded-full px-3 py-2 border border-gray-200">
          <button
            onClick={() => setMode('individual')}
            className={`text-[12px] font-semibold px-3 py-1 rounded-full transition-colors ${
              mode === 'individual' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            단독 뷰
          </button>
          <button
            onClick={() => setMode('overview')}
            className={`text-[12px] font-semibold px-3 py-1 rounded-full transition-colors ${
              mode === 'overview' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            5화면 검토
          </button>
        </div>
      )}
      {activeMode === 'overview' ? <OverviewPage /> : <IndividualPage />}
    </div>
  );
}
