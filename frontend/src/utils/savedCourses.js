export const SAVED_COURSES_KEY = 'saved_courses_v1';
export const MAX_SAVED_COURSES = 30;

function getStorage() {
  if (typeof window === 'undefined' || !window.localStorage) return null;
  return window.localStorage;
}

function safeParse(raw) {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter(isValidSavedCourse) : [];
  } catch {
    return [];
  }
}

function isValidSavedCourse(course) {
  return (
    course &&
    typeof course === 'object' &&
    typeof course.course_id === 'string' &&
    typeof course.region === 'string' &&
    Array.isArray(course.places)
  );
}

function normalizeCourse(course) {
  const now = new Date().toISOString();
  const courseId = String(course.course_id || course.id || `local-${Date.now()}`);
  const places = Array.isArray(course.places) ? course.places : [];
  const summary =
    course.summary ||
    places.slice(0, 3).map((place) => place.name).filter(Boolean).join(' · ');

  return {
    course_id: courseId,
    region: course.region || course.displayRegion || '여행 코스',
    created_at: course.created_at || now,
    updated_at: now,
    summary,
    place_count: places.length,
    total_duration_min: course.total_duration_min ?? null,
    total_travel_min: course.total_travel_min ?? null,
    option_notice: course.option_notice ?? null,
    missing_slot_reason: course.missing_slot_reason ?? null,
    generation_params: normalizeGenerationParams(course.generation_params || course.params || course),
    places: places.map((place, index) => ({
      order: index + 1,
      place_id: place.place_id ?? place.id ?? null,
      name: place.name || '',
      role: place.role || place.visit_role || '',
      description: place.description || '',
      image: place.image || place.first_image_url || null,
      time: place.time || place.scheduled_start || null,
      duration: place.duration || null,
      lat: place.lat ?? place.latitude ?? null,
      lon: place.lon ?? place.longitude ?? null,
    })),
  };
}

function normalizeGenerationParams(params) {
  const allowed = [
    'region',
    'displayRegion',
    'departure_time',
    'region_travel_type',
    'start_lat',
    'start_lon',
    'start_anchor',
    'zone_id',
    '_homeAnchor',
    'mood',
    'walk',
    'density',
  ];
  const normalized = {};
  for (const key of allowed) {
    if (params?.[key] !== undefined && params?.[key] !== null && params?.[key] !== '') {
      normalized[key] = params[key];
    }
  }
  if (!normalized.displayRegion && params?.region) {
    normalized.displayRegion = params.region;
  }
  return normalized;
}

export function loadSavedCourses() {
  const storage = getStorage();
  if (!storage) {
    return { ok: false, courses: [], error: 'STORAGE_UNAVAILABLE' };
  }
  try {
    return {
      ok: true,
      courses: safeParse(storage.getItem(SAVED_COURSES_KEY)),
      error: null,
    };
  } catch {
    return { ok: false, courses: [], error: 'STORAGE_UNAVAILABLE' };
  }
}

export function saveCourseToLocalStorage(course) {
  const storage = getStorage();
  if (!storage) {
    return { ok: false, course: null, courses: [], error: 'STORAGE_UNAVAILABLE' };
  }
  try {
    const nextCourse = normalizeCourse(course);
    const current = safeParse(storage.getItem(SAVED_COURSES_KEY));
    const deduped = current.filter((item) => String(item.course_id) !== nextCourse.course_id);
    const courses = [nextCourse, ...deduped].slice(0, MAX_SAVED_COURSES);
    storage.setItem(SAVED_COURSES_KEY, JSON.stringify(courses));
    return { ok: true, course: nextCourse, courses, error: null };
  } catch {
    return { ok: false, course: null, courses: [], error: 'STORAGE_UNAVAILABLE' };
  }
}

export function deleteSavedCourse(courseId) {
  const storage = getStorage();
  if (!storage) {
    return { ok: false, courses: [], error: 'STORAGE_UNAVAILABLE' };
  }
  try {
    const current = safeParse(storage.getItem(SAVED_COURSES_KEY));
    const courses = current.filter((item) => String(item.course_id) !== String(courseId));
    storage.setItem(SAVED_COURSES_KEY, JSON.stringify(courses));
    return { ok: true, courses, error: null };
  } catch {
    return { ok: false, courses: [], error: 'STORAGE_UNAVAILABLE' };
  }
}

export function getSavedCourse(courseId) {
  const result = loadSavedCourses();
  if (!result.ok) return { ok: false, course: null, error: result.error };
  const course = result.courses.find((item) => String(item.course_id) === String(courseId));
  return { ok: true, course: course || null, error: course ? null : 'COURSE_NOT_FOUND' };
}

export function getRegenerateParams(course) {
  if (!isValidSavedCourse(course)) {
    return { ok: false, params: null, warnings: ['INVALID_SAVED_COURSE'] };
  }

  const warnings = [];
  const params = {
    ...(course.generation_params && typeof course.generation_params === 'object'
      ? course.generation_params
      : {}),
  };

  if (!params.region && course.region) {
    params.region = course.region;
    warnings.push('LEGACY_REGION_FALLBACK');
  }
  if (!params.displayRegion && course.region) {
    params.displayRegion = course.region;
  }
  if (!params.region) {
    return { ok: false, params: null, warnings: ['REGION_MISSING'] };
  }

  return { ok: true, params, warnings };
}

export function clearSavedCoursesForTest() {
  const storage = getStorage();
  if (storage) storage.removeItem(SAVED_COURSES_KEY);
}
