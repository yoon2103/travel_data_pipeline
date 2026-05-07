// 모바일 앱 껍데기 - 상태바 + 바텀탭 포함
export default function MobileShell({ children, activeTab = 'home', onTabChange }) {
  const tabs = [
    { id: 'home', label: '홈', icon: HomeIcon },
    { id: 'saved', label: '저장', icon: HeartIcon },
    { id: 'my', label: '마이', icon: UserIcon },
  ];

  return (
    <div className="relative w-full h-[100dvh] bg-white overflow-hidden flex flex-col sm:w-[390px] sm:h-[844px] sm:rounded-[40px] sm:shadow-2xl sm:border sm:border-gray-200">
      {/* 상태바 */}
      <div className="flex items-center justify-between px-6 pb-1 bg-white shrink-0 sm:pt-3" style={{ paddingTop: 'calc(12px + env(safe-area-inset-top, 0px))' }}>
        <span className="text-[13px] font-semibold text-gray-900">9:41</span>
        <div className="flex items-center gap-1.5">
          <svg width="16" height="12" viewBox="0 0 16 12" fill="none">
            <rect x="0" y="3" width="3" height="9" rx="1" fill="#1a1a1a"/>
            <rect x="4.5" y="2" width="3" height="10" rx="1" fill="#1a1a1a"/>
            <rect x="9" y="0" width="3" height="12" rx="1" fill="#1a1a1a"/>
            <rect x="13.5" y="0" width="3" height="12" rx="1" fill="#e5e7eb"/>
          </svg>
          <svg width="16" height="12" viewBox="0 0 16 12" fill="none">
            <path d="M8 2.5a6 6 0 00-4.5 2L1 7l7 5 7-5-2.5-2.5A6 6 0 008 2.5z" fill="#1a1a1a"/>
          </svg>
          <svg width="22" height="12" viewBox="0 0 22 12" fill="none">
            <rect x="1" y="1" width="18" height="10" rx="3" stroke="#1a1a1a" strokeWidth="1.5"/>
            <rect x="2" y="2" width="13" height="8" rx="2" fill="#1a1a1a"/>
            <path d="M20 4h1a1 1 0 011 1v2a1 1 0 01-1 1h-1V4z" fill="#1a1a1a"/>
          </svg>
        </div>
      </div>

      {/* 메인 화면 (스크롤 영역) */}
      <div className="flex-1 overflow-hidden relative bg-gray-50 flex flex-col">
        <div className="flex-1 overflow-y-auto hide-scrollbar">
          {children}
        </div>
      </div>

      {/* 하단 탭바 👉 여기에 id="main-bottom-tab" 을 추가했습니다! */}
      <div 
        id="main-bottom-tab" 
        className="flex items-center justify-around bg-white border-t border-gray-100 shrink-0 sm:rounded-b-[40px] transition-opacity duration-200"
        style={{ height: 'calc(84px + env(safe-area-inset-bottom, 0px))', paddingBottom: 'calc(20px + env(safe-area-inset-bottom, 0px))' }}
      >
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className="flex-1 flex flex-col items-center gap-0.5"
            >
              <Icon active={isActive} />
              <span className={`text-[10px] font-medium ${isActive ? 'text-blue-600' : 'text-gray-400'}`}>
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function HomeIcon({ active }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
      <path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H5a1 1 0 01-1-1V9.5z"
        stroke={active ? '#2563eb' : '#9ca3af'} strokeWidth="1.8" fill={active ? '#dbeafe' : 'none'}/>
      <path d="M9 21V12h6v9" stroke={active ? '#2563eb' : '#9ca3af'} strokeWidth="1.8"/>
    </svg>
  );
}

function HeartIcon({ active }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
      <path d="M12 21C12 21 3 14.5 3 8.5A4.5 4.5 0 017.5 4c1.8 0 3.2.9 4.5 2 1.3-1.1 2.7-2 4.5-2A4.5 4.5 0 0121 8.5c0 6-9 12.5-9 12.5z"
        stroke={active ? '#2563eb' : '#9ca3af'} strokeWidth="1.8" fill={active ? '#dbeafe' : 'none'}/>
    </svg>
  );
}

function UserIcon({ active }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
      <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" stroke={active ? '#2563eb' : '#9ca3af'} strokeWidth="1.8"/>
      <circle cx="12" cy="7" r="4" stroke={active ? '#2563eb' : '#9ca3af'} strokeWidth="1.8" fill={active ? '#dbeafe' : 'none'}/>
    </svg>
  );
}
