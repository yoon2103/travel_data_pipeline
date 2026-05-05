export const REGIONS = ['서울', '부산', '대구', '인천', '광주', '대전', '제주', '경주', '강릉', '전주'];

export const REGION_TO_DB = {
  서울: '서울',
  부산: '부산',
  대구: '대구',
  인천: '인천',
  광주: '광주',
  대전: '대전',
  제주: '제주',
  경주: '경북',
  강릉: '강원',
  전주: '전북',
};

export const MOOD_TO_THEMES = {
  '자연 선택':  ['nature'],
  '도심 감성':  ['urban'],
  '카페 투어':  ['cafe'],
  '맛집 탐방':  ['food'],
  '역사 문화':  ['history'],
  '조용한 산책': ['walk'],
};

export const HERO_IMAGES = {
  city:     'https://images.unsplash.com/photo-1534430480872-3498386e7856?w=800&q=80',
  sea:      'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&q=80',
  valley:   'https://images.unsplash.com/photo-1448375240586-882707db888b?w=800&q=80',
  mountain: 'https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=800&q=80',
};

export const REGION_HERO_MAP = {
  서울: 'city',
  대구: 'city',
  대전: 'city',
  경주: 'city',
  전주: 'city',
  광주: 'valley',
  인천: 'sea',
  부산: 'sea',
  강릉: 'sea',
  제주: 'sea',
};

export function getHeroImage(region) {
  const key = REGION_HERO_MAP[region] || 'city';
  return HERO_IMAGES[key];
}

export const COMPANIONS = ['혼자', '둘이서', '가족', '친구들'];

export const MOODS = ['자연 선택', '도심 감성', '카페 투어', '맛집 탐방', '역사 문화', '조용한 산책'];

export const WALK_LEVELS = ['적게', '보통', '조금 멀어도 좋아요'];

export const DENSITY_LEVELS = ['여유롭게', '적당히', '알차게'];

// 백엔드 API 실패 시 정적 fallback anchor — DB 검증 없는 좌표/이름만 포함
// key = DB region_1 값 (REGION_TO_DB 결과값과 동일)
export const STATIC_ANCHORS = {
  '서울': [
    { zone_id: 'seoul_gangnam',     name: '강남역 주변',      center_lat: 37.4979, center_lon: 127.0276 },
    { zone_id: 'seoul_hongdae',     name: '홍대입구 주변',    center_lat: 37.5563, center_lon: 126.9236 },
    { zone_id: 'seoul_myeongdong',  name: '명동/을지로 주변', center_lat: 37.5636, center_lon: 126.9826 },
    { zone_id: 'seoul_gwanghwamun', name: '광화문/종로 주변', center_lat: 37.5759, center_lon: 126.9769 },
    { zone_id: 'seoul_seongsu',     name: '성수동/건대 주변', center_lat: 37.5443, center_lon: 127.0558 },
  ],
  '부산': [
    { zone_id: 'busan_haeundae',    name: '해운대 주변',      center_lat: 35.1588, center_lon: 129.1604 },
    { zone_id: 'busan_gwanganli',   name: '광안리 주변',      center_lat: 35.1527, center_lon: 129.1183 },
    { zone_id: 'busan_seomyeon',    name: '서면 주변',        center_lat: 35.1569, center_lon: 129.0587 },
    { zone_id: 'busan_nampodong',   name: '남포동/부산역 주변', center_lat: 35.1038, center_lon: 129.0317 },
  ],
  '대구': [
    { zone_id: 'daegu_dongseongno', name: '동성로 주변',      center_lat: 35.8703, center_lon: 128.5960 },
    { zone_id: 'daegu_dongdaegu',   name: '동대구역 주변',    center_lat: 35.8799, center_lon: 128.6291 },
    { zone_id: 'daegu_suseongmot',  name: '수성못 주변',      center_lat: 35.8452, center_lon: 128.6280 },
  ],
  '인천': [
    { zone_id: 'incheon_chinatown', name: '인천역/차이나타운 주변', center_lat: 37.4738, center_lon: 126.6168 },
    { zone_id: 'incheon_wolmi',     name: '월미도 주변',      center_lat: 37.4742, center_lon: 126.5983 },
    { zone_id: 'incheon_songdo',    name: '송도 주변',        center_lat: 37.3905, center_lon: 126.6478 },
  ],
  '광주': [
    { zone_id: 'gwangju_station',    name: '광주역 주변',     center_lat: 35.1600, center_lon: 126.9042 },
    { zone_id: 'gwangju_chungjangno',name: '충장로/동명동 주변', center_lat: 35.1472, center_lon: 126.9148 },
  ],
  '대전': [
    { zone_id: 'daejeon_station',   name: '대전역 주변',      center_lat: 36.3315, center_lon: 127.4346 },
    { zone_id: 'daejeon_dunsan',    name: '둔산/시청 주변',   center_lat: 36.3505, center_lon: 127.3849 },
    { zone_id: 'daejeon_yuseong',   name: '유성온천 주변',    center_lat: 36.3618, center_lon: 127.3386 },
  ],
  '제주': [
    { zone_id: 'jeju_city',         name: '제주공항 주변',    center_lat: 33.5113, center_lon: 126.4941 },
    { zone_id: 'jeju_aewol',        name: '애월 주변',        center_lat: 33.4640, center_lon: 126.3175 },
    { zone_id: 'jeju_jungmun',      name: '중문 주변',        center_lat: 33.2541, center_lon: 126.4122 },
    { zone_id: 'jeju_seongsan',     name: '성산 주변',        center_lat: 33.4580, center_lon: 126.9405 },
  ],
  '경북': [
    { zone_id: 'gyeongbuk_hwangni',  name: '황리단길/대릉원 주변', center_lat: 35.8342, center_lon: 129.2259 },
    { zone_id: 'gyeongbuk_gyeongju', name: '경주역 주변',    center_lat: 35.8392, center_lon: 129.2101 },
    { zone_id: 'gyeongbuk_bulguksa', name: '불국사 주변',    center_lat: 35.7888, center_lon: 129.3315 },
  ],
  '강원': [
    { zone_id: 'gangwon_gangneung',  name: '강릉역 주변',     center_lat: 37.7750, center_lon: 128.9400 },
    { zone_id: 'gangwon_gyeongpo',   name: '경포해변 주변',   center_lat: 37.7988, center_lon: 128.9046 },
    { zone_id: 'gangwon_sokcho',     name: '속초 주변',       center_lat: 38.2070, center_lon: 128.5918 },
  ],
  '전북': [
    { zone_id: 'jeonbuk_hanok',     name: '전주한옥마을 주변', center_lat: 35.8180, center_lon: 127.1524 },
    { zone_id: 'jeonbuk_station',   name: '전주역 주변',      center_lat: 35.8178, center_lon: 127.1490 },
    { zone_id: 'jeonbuk_gunsan',    name: '군산 주변',        center_lat: 35.9675, center_lon: 126.7368 },
  ],
};
