import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { etaService } from '@/services/eta.service';
import type { WeatherData } from '@/types/dashboard.types';

export interface WeatherContextValue {
  weather: WeatherData | null;
  navbarWeather: {
    temperature: string;
    condition: string;
    apparentTemperature?: string | undefined;
  } | null;
  isLoading: boolean;
  isRefreshing: boolean;
  status: 'AVAILABLE' | 'UNAVAILABLE' | 'LOADING';
  provenance: string;
  observedAt: string | null;
  locationName: string | null;
  latitude: number | null;
  longitude: number | null;
  lastUpdated: Date | null;
  error: string | null;
  refreshWeather: (force?: boolean) => Promise<void>;
}

const WeatherContext = createContext<WeatherContextValue | undefined>(undefined);

// 5-minute background refresh interval (300,000 ms)
const REFRESH_INTERVAL_MS = 5 * 60 * 1000;

// Movement threshold (~0.005 degrees ≈ 500 meters) to trigger immediate weather refresh for new coordinates
const MOVEMENT_THRESHOLD_DEG = 0.005;

export const WeatherProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [navbarWeather, setNavbarWeather] = useState<{
    temperature: string;
    condition: string;
    apparentTemperature?: string | undefined;
  } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [status, setStatus] = useState<'AVAILABLE' | 'UNAVAILABLE' | 'LOADING'>('LOADING');
  const [provenance, setProvenance] = useState<string>('UNAVAILABLE');
  const [observedAt, setObservedAt] = useState<string | null>(null);
  const [locationName, setLocationName] = useState<string | null>(null);
  const [latitude, setLatitude] = useState<number | null>(null);
  const [longitude, setLongitude] = useState<number | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  // References to preserve last valid data across background refreshes and avoid flickers
  const lastValidWeatherRef = useRef<WeatherData | null>(null);
  const lastValidNavbarRef = useRef<{
    temperature: string;
    condition: string;
    apparentTemperature?: string | undefined;
  } | null>(null);
  const lastCoordsRef = useRef<{ lat: number; lon: number } | null>(null);
  const userCoordsRef = useRef<{ lat: number; lon: number } | null>(null);
  const lastFetchTimeRef = useRef<number>(0);
  const isFetchingRef = useRef<boolean>(false);

  /**
   * Resolve coordinates exclusively from the browser's real navigator.geolocation.
   * Never falls back to hardcoded cities or default coordinates.
   */
  const resolveBrowserLocation = useCallback(async (): Promise<{ lat: number; lon: number } | null> => {
    if (typeof window === 'undefined' || !('geolocation' in navigator)) {
      return null;
    }

    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const coords = { lat: pos.coords.latitude, lon: pos.coords.longitude };
          userCoordsRef.current = coords;
          resolve(coords);
        },
        (err) => {
          // If permission was denied, do not invent coordinates
          if (err.code === 1) {
            console.warn('[WeatherContext] Location permission denied by user.');
          } else {
            console.warn('[WeatherContext] Location resolution error:', err.message);
          }
          // If we already had coordinates from a watcher or previous reading, reuse them
          resolve(userCoordsRef.current);
        },
        {
          timeout: 8000,
          maximumAge: 60000,
          enableHighAccuracy: false,
        },
      );
    });
  }, []);

  /**
   * Fetch live weather from real Open-Meteo API using genuine GPS coordinates.
   */
  const fetchRealWeather = useCallback(
    async (force = false, explicitCoords?: { lat: number; lon: number }) => {
      // Prevent overlapping duplicate requests
      if (isFetchingRef.current) return;

      const now = Date.now();
      // Cache prevents duplicate calls within interval unless forced
      if (
        !force &&
        lastFetchTimeRef.current &&
        now - lastFetchTimeRef.current < REFRESH_INTERVAL_MS &&
        lastValidWeatherRef.current
      ) {
        return;
      }

      isFetchingRef.current = true;

      // Last-valid data retention:
      // If we already have valid weather data, mark isRefreshing=true. DO NOT clear to null or set loading=true!
      if (lastValidWeatherRef.current) {
        setIsRefreshing(true);
      } else {
        setIsLoading(true);
        setStatus('LOADING');
      }

      try {
        // Resolve coordinates strictly from browser GPS fix
        const coords = explicitCoords || (await resolveBrowserLocation()) || userCoordsRef.current;

        if (!coords || coords.lat == null || coords.lon == null) {
          // No location available — truthful message, no invented location
          const permMsg = 'Weather unavailable — location permission required';
          if (!lastValidWeatherRef.current) {
            setWeather(null);
            setNavbarWeather(null);
            setStatus('UNAVAILABLE');
            setProvenance('UNAVAILABLE');
            setObservedAt(null);
            setLocationName(null);
            setLatitude(null);
            setLongitude(null);
            setError(permMsg);
          } else {
            // Keep last valid observation visible
            setError(permMsg);
          }
          return;
        }

        const targetLat = coords.lat;
        const targetLon = coords.lon;
        const targetLocation = 'Current Device Location';

        // Query backend Open-Meteo proxy endpoint
        const res = await etaService.getLiveWeather(targetLat, targetLon);

        if (res.status === 'AVAILABLE') {
          const tempFormatted =
            res.temperature || (res.temperature_c != null ? `${res.temperature_c.toFixed(1)}°C` : '');
          const appTempFormatted =
            res.apparent_temperature ||
            (res.apparent_temperature_c != null ? `${res.apparent_temperature_c.toFixed(1)}°C` : undefined);
          const condFormatted = res.condition || 'Live Weather';
          const impactMinutes = res.impact_minutes || 0;
          const impactSeverity: 'low' | 'moderate' | 'high' =
            impactMinutes > 10 ? 'high' : impactMinutes > 0 ? 'moderate' : 'low';
          const statusText =
            impactMinutes > 10 ? 'High Impact' : impactMinutes > 0 ? 'Medium Impact' : 'Low Impact';

          const dashboardData: WeatherData = {
            condition: condFormatted,
            temperature: tempFormatted,
            temperature_c: res.temperature_c,
            apparentTemperature: appTempFormatted,
            apparentTemperature_c: res.apparent_temperature_c,
            location: targetLocation,
            latitude: targetLat,
            longitude: targetLon,
            impact: statusText,
            etaImpact:
              impactMinutes > 0
                ? `Estimated transit delay: +${impactMinutes} minutes`
                : 'Clear transit conditions, no weather delay',
            impactSeverity,
            windSpeed: res.wind_speed || '0.0 km/h',
            windSpeed_kmh: res.wind_speed_kmh,
            windDirection: res.wind_direction || undefined,
            windDirectionDeg: res.wind_direction_deg,
            humidity: res.humidity || (res.humidity_percent != null ? `${res.humidity_percent.toFixed(0)}%` : '--'),
            humidityPercent: res.humidity_percent,
            precipitation:
              res.precipitation || (res.precipitation_mm != null ? `${res.precipitation_mm.toFixed(1)} mm` : '0.0 mm'),
            precipitation_mm: res.precipitation_mm,
            precipitationProbability: res.precipitation_probability
              ? `${res.precipitation_probability} forecast`
              : null,
            precipitationProbabilityPercent: res.precipitation_probability_percent,
            observedAt: res.sampled_at || new Date().toISOString(),
            provenance: res.provenance || 'REAL',
          };

          const navData = {
            temperature: tempFormatted,
            condition: condFormatted,
            apparentTemperature: appTempFormatted,
          };

          // Cache last valid state
          lastValidWeatherRef.current = dashboardData;
          lastValidNavbarRef.current = navData;
          lastCoordsRef.current = { lat: targetLat, lon: targetLon };
          userCoordsRef.current = { lat: targetLat, lon: targetLon };

          setWeather(dashboardData);
          setNavbarWeather(navData);
          setStatus('AVAILABLE');
          setProvenance(res.provenance || 'REAL');
          setObservedAt(res.sampled_at || new Date().toISOString());
          setLocationName(targetLocation);
          setLatitude(targetLat);
          setLongitude(targetLon);
          setLastUpdated(new Date());
          setError(null);
        } else {
          // Provider returned non-available response
          if (lastValidWeatherRef.current) {
            setError('Live weather provider feed temporarily degraded; retaining last observation.');
          } else {
            setWeather(null);
            setNavbarWeather(null);
            setStatus('UNAVAILABLE');
            setProvenance('UNAVAILABLE');
            setObservedAt(null);
            setLocationName(null);
            setLatitude(null);
            setLongitude(null);
            setError('Weather telemetry unavailable.');
          }
        }
      } catch (err: unknown) {
        console.warn('[WeatherContext] Live weather retrieval failed:', err);
        // Retain last valid weather on network error to prevent flicker!
        if (lastValidWeatherRef.current) {
          setError('Network interruption refreshing weather; retaining last valid telemetry.');
        } else {
          setWeather(null);
          setNavbarWeather(null);
          setStatus('UNAVAILABLE');
          setProvenance('UNAVAILABLE');
          setObservedAt(null);
          setLocationName(null);
          setLatitude(null);
          setLongitude(null);
          setError('Weather unavailable — location permission required');
        }
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
        isFetchingRef.current = false;
        lastFetchTimeRef.current = Date.now();
      }
    },
    [resolveBrowserLocation],
  );

  // Initial fetch on mount & automatic continuous background refresh (5 minutes)
  useEffect(() => {
    // 1. Initial fetch on mount
    fetchRealWeather();

    // 2. Continuous 5-minute background polling timer
    const intervalId = setInterval(() => {
      fetchRealWeather(true);
    }, REFRESH_INTERVAL_MS);

    // 3. Tab visibility / window focus listener (refresh if stale when returning to tab)
    const handleActivityChange = () => {
      if (document.visibilityState === 'visible') {
        const timeSinceLast = Date.now() - lastFetchTimeRef.current;
        if (timeSinceLast >= REFRESH_INTERVAL_MS) {
          fetchRealWeather(true);
        }
      }
    };

    document.addEventListener('visibilitychange', handleActivityChange);
    window.addEventListener('focus', handleActivityChange);

    // 4. Geolocation movement listener (detects genuine movement > ~500m or new fix)
    let watchId: number | null = null;
    if (typeof window !== 'undefined' && 'geolocation' in navigator) {
      try {
        watchId = navigator.geolocation.watchPosition(
          (pos) => {
            const newLat = pos.coords.latitude;
            const newLon = pos.coords.longitude;
            userCoordsRef.current = { lat: newLat, lon: newLon };

            if (lastCoordsRef.current) {
              const dLat = Math.abs(newLat - lastCoordsRef.current.lat);
              const dLon = Math.abs(newLon - lastCoordsRef.current.lon);
              if (dLat >= MOVEMENT_THRESHOLD_DEG || dLon >= MOVEMENT_THRESHOLD_DEG) {
                // Moved significantly — refresh weather immediately for new coordinates
                fetchRealWeather(true, { lat: newLat, lon: newLon });
              }
            } else {
              // First location fix obtained from watchPosition
              fetchRealWeather(false, { lat: newLat, lon: newLon });
            }
          },
          (err) => {
            if (err.code === 1) {
              // Permission denied
              if (!lastValidWeatherRef.current) {
                setStatus('UNAVAILABLE');
                setError('Weather unavailable — location permission required');
              }
            }
          },
          { maximumAge: 30000, timeout: 15000, enableHighAccuracy: false },
        );
      } catch {
        // Geolocation watch not permitted
      }
    }

    return () => {
      clearInterval(intervalId);
      document.removeEventListener('visibilitychange', handleActivityChange);
      window.removeEventListener('focus', handleActivityChange);
      if (watchId !== null && typeof window !== 'undefined' && 'geolocation' in navigator) {
        navigator.geolocation.clearWatch(watchId);
      }
    };
  }, [fetchRealWeather]);

  const refreshWeather = useCallback(
    async (force = true) => {
      await fetchRealWeather(force);
    },
    [fetchRealWeather],
  );

  return (
    <WeatherContext.Provider
      value={{
        weather,
        navbarWeather,
        isLoading,
        isRefreshing,
        status,
        provenance,
        observedAt,
        locationName,
        latitude,
        longitude,
        lastUpdated,
        error,
        refreshWeather,
      }}
    >
      {children}
    </WeatherContext.Provider>
  );
};

export const useWeather = (): WeatherContextValue => {
  const context = useContext(WeatherContext);
  if (!context) {
    throw new Error('useWeather must be used within a WeatherProvider');
  }
  return context;
};
