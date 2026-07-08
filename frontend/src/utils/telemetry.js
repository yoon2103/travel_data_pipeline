const isBrowser = typeof window !== 'undefined';

export const trackEvent = (eventName, payload = {}) => {
  if (!eventName || !isBrowser) return;
  if (window.__TRAVEL_TELEMETRY_DEBUG__ === true) {
    console.debug('[travel-telemetry]', eventName, payload);
  }
};

export const courseTelemetryContext = (params = {}) => ({
  region: params.region || '',
  selectedAnchor: params.selected_anchor || params.selectedAnchor || '',
  theme: params.theme || '',
  mood: params.mood || '',
  departureTime: params.departure_time || params.departureTime || '',
});
