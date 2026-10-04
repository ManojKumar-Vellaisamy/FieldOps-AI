import { useState, useEffect, useRef, useCallback } from 'react';
import { technicianService } from '@/services/technician.service';
import type { GeolocationFreshness } from '@/types/realtime.types';

export interface ManualLocationData {
  latitude: number;
  longitude: number;
  label?: string;
  timestamp: number;
}

export const MANUAL_LOCATION_STORAGE_KEY = 'fieldops_technician_manual_location';

function calculateHaversineMiles(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 3958.8; // Earth radius in miles
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

export interface GeolocationState {
  coordinates: {
    latitude: number;
    longitude: number;
    accuracy?: number;
  } | null;
  freshness: GeolocationFreshness;
  permissionState: 'prompt' | 'granted' | 'denied' | 'unsupported';
  lastUpdated: Date | null;
  errorMessage: string | null;
  isTracking: boolean;
  requestPermission: () => void;
  isManualOverride: boolean;
  manualLabel: string | null;
  setManualLocation: (lat: number, lon: number, label?: string) => Promise<void>;
  clearManualOverride: () => Promise<void>;
}

interface UseTechnicianGeolocationOptions {
  enabled?: boolean;
  throttleIntervalMs?: number;
  onLocationSent?: (coords: { latitude: number; longitude: number }) => void;
}

export function useTechnicianGeolocation({
  enabled = true,
  throttleIntervalMs = 12000,
  onLocationSent,
}: UseTechnicianGeolocationOptions = {}): GeolocationState {
  // Check localStorage for any active manual override
  const getStoredOverride = (): ManualLocationData | null => {
    try {
      const stored = localStorage.getItem(MANUAL_LOCATION_STORAGE_KEY);
      if (stored) {
        return JSON.parse(stored) as ManualLocationData;
      }
    } catch {
      // Ignore parse errors
    }
    return null;
  };

  const initialOverride = getStoredOverride();

  const [coordinates, setCoordinates] = useState<{
    latitude: number;
    longitude: number;
    accuracy?: number;
  } | null>(
    initialOverride
      ? { latitude: initialOverride.latitude, longitude: initialOverride.longitude, accuracy: 5 }
      : null,
  );
  const [isManualOverride, setIsManualOverride] = useState<boolean>(!!initialOverride);
  const [manualLabel, setManualLabel] = useState<string | null>(initialOverride?.label || null);
  const [freshness, setFreshness] = useState<GeolocationFreshness>(
    initialOverride ? 'LIVE' : 'UNAVAILABLE',
  );
  const [permissionState, setPermissionState] = useState<
    'prompt' | 'granted' | 'denied' | 'unsupported'
  >(initialOverride ? 'granted' : 'prompt');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(
    initialOverride ? new Date(initialOverride.timestamp) : null,
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isTracking, setIsTracking] = useState<boolean>(false);

  const watchIdRef = useRef<number | null>(null);
  const lastSentTimestampRef = useRef<number>(0);
  const lastCoordinatesRef = useRef<{ latitude: number; longitude: number } | null>(
    initialOverride ? { latitude: initialOverride.latitude, longitude: initialOverride.longitude } : null,
  );
  const manualOverrideRef = useRef<ManualLocationData | null>(initialOverride);
  const serverLocationRef = useRef<{ latitude: number; longitude: number } | null>(null);

  // Load technician authoritative stationed location from backend profile on mount
  useEffect(() => {
    let isCancelled = false;
    technicianService
      .getMyProfile()
      .then((profile) => {
        if (isCancelled || !profile) return;
        if (
          typeof profile.current_latitude === 'number' &&
          typeof profile.current_longitude === 'number'
        ) {
          const serverCoords = {
            latitude: profile.current_latitude,
            longitude: profile.current_longitude,
          };
          serverLocationRef.current = serverCoords;

          // If no active manual override in localStorage, initialize coordinates with server stationed location!
          if (!manualOverrideRef.current) {
            setCoordinates({
              latitude: serverCoords.latitude,
              longitude: serverCoords.longitude,
              accuracy: 5,
            });
            setFreshness('LIVE');
            setPermissionState('granted');
            setLastUpdated(
              profile.location_updated_at ? new Date(profile.location_updated_at) : new Date(),
            );
          }
        }
      })
      .catch(() => {
        // Ignore if unauthenticated or network error
      });

    return () => {
      isCancelled = true;
    };
  }, []);

  // Sync state with cross-component or cross-tab manual location updates
  useEffect(() => {
    const handleStorageOrCustomEvent = () => {
      const current = getStoredOverride();
      manualOverrideRef.current = current;
      if (current) {
        setIsManualOverride(true);
        setManualLabel(current.label || 'Manual Calibration');
        setCoordinates({ latitude: current.latitude, longitude: current.longitude, accuracy: 5 });
        setFreshness('LIVE');
        setPermissionState('granted');
        setLastUpdated(new Date(current.timestamp));
      } else {
        setIsManualOverride(false);
        setManualLabel(null);
      }
    };

    window.addEventListener('fieldops:technician_location_updated', handleStorageOrCustomEvent);
    window.addEventListener('storage', handleStorageOrCustomEvent);
    return () => {
      window.removeEventListener('fieldops:technician_location_updated', handleStorageOrCustomEvent);
      window.removeEventListener('storage', handleStorageOrCustomEvent);
    };
  }, []);

  // Check browser capability and permission status
  useEffect(() => {
    if (!('geolocation' in navigator)) {
      if (!manualOverrideRef.current && !serverLocationRef.current) {
        setPermissionState('unsupported');
        setFreshness('UNAVAILABLE');
        setErrorMessage('Browser does not support the Geolocation API.');
      }
      return;
    }

    if (navigator.permissions && navigator.permissions.query) {
      navigator.permissions
        .query({ name: 'geolocation' })
        .then((perm) => {
          if (!manualOverrideRef.current && !serverLocationRef.current) {
            setPermissionState(perm.state as 'prompt' | 'granted' | 'denied');
          }
          perm.onchange = () => {
            if (!manualOverrideRef.current && !serverLocationRef.current) {
              setPermissionState(perm.state as 'prompt' | 'granted' | 'denied');
            }
          };
        })
        .catch(() => {
          // Permissions API query not supported for geolocation in some browsers
        });
    }
  }, []);

  // Send real location to backend with throttling
  const sendLocationToBackend = useCallback(
    async (lat: number, lon: number, recordedAtIso?: string, force = false) => {
      const now = Date.now();
      const elapsed = now - lastSentTimestampRef.current;
      const last = lastCoordinatesRef.current;

      const hasMoved =
        !last || Math.abs(last.latitude - lat) > 0.00015 || Math.abs(last.longitude - lon) > 0.00015;

      if (!force && elapsed < throttleIntervalMs && !hasMoved) {
        return;
      }

      try {
        lastSentTimestampRef.current = now;
        lastCoordinatesRef.current = { latitude: lat, longitude: lon };
        await technicianService.updateMyLocation(lat, lon, recordedAtIso);
        if (onLocationSent) {
          onLocationSent({ latitude: lat, longitude: lon });
        }
      } catch (err) {
        console.warn('[Geolocation] Failed to sync location telemetry to backend:', err);
      }
    },
    [throttleIntervalMs, onLocationSent],
  );

  // Freshness watchdog (downgrades to STALE if no new fix in 60s, skipped if manual override or server stationed location)
  useEffect(() => {
    const watchdogInterval = setInterval(() => {
      if (manualOverrideRef.current || serverLocationRef.current) return;
      if (lastUpdated && freshness === 'LIVE') {
        const ageMs = Date.now() - lastUpdated.getTime();
        if (ageMs > 60000) {
          setFreshness('STALE');
        }
      }
    }, 10000);

    return () => clearInterval(watchdogInterval);
  }, [lastUpdated, freshness]);

  // Main tracking effect
  useEffect(() => {
    if (!enabled) {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
      setIsTracking(false);
      return;
    }

    if (!('geolocation' in navigator)) {
      return;
    }

    setIsTracking(true);
    setErrorMessage(null);

    const handleSuccess = (position: GeolocationPosition) => {
      // 1. If manual override is active, do not allow stale browser Wi-Fi coordinates to overwrite
      if (manualOverrideRef.current) {
        return;
      }

      const lat = position.coords.latitude;
      const lon = position.coords.longitude;
      const accuracy = position.coords.accuracy;
      const fixDate = new Date(position.timestamp);

      // 2. Discrepancy protection for laptops/desktops:
      // If the technician has an authoritative stationed location on the server (configured by admin or saved),
      // and the browser reports coordinates > 15 miles away (e.g. laptop Wi-Fi cache jumping to Coimbatore 170 miles away),
      // DO NOT silently overwrite the technician's location with inaccurate laptop Wi-Fi coordinates!
      if (serverLocationRef.current) {
        const distMiles = calculateHaversineMiles(
          lat,
          lon,
          serverLocationRef.current.latitude,
          serverLocationRef.current.longitude,
        );
        if (distMiles > 15) {
          console.warn(
            `[Geolocation] Protecting technician stationed location (${serverLocationRef.current.latitude}, ${serverLocationRef.current.longitude}). ` +
              `Ignoring discrepant browser Wi-Fi location (${lat}, ${lon}) which is ${distMiles.toFixed(1)} miles away.`,
          );
          return; // PRESERVE SERVER LOCATION
        }
      }

      setCoordinates({ latitude: lat, longitude: lon, accuracy });
      setLastUpdated(fixDate);
      setFreshness('LIVE');
      setPermissionState('granted');
      setErrorMessage(null);

      sendLocationToBackend(lat, lon, fixDate.toISOString());
    };

    const handleError = (error: GeolocationPositionError) => {
      if (manualOverrideRef.current || serverLocationRef.current) {
        return;
      }
      console.warn('[Geolocation] Geolocation error:', error.code, error.message);
      if (error.code === error.PERMISSION_DENIED) {
        setPermissionState('denied');
        setFreshness('UNAVAILABLE');
        setErrorMessage('Location permission was denied in your browser settings.');
      } else if (error.code === error.POSITION_UNAVAILABLE) {
        setFreshness('UNAVAILABLE');
        setErrorMessage('GPS signal is currently unavailable on your device.');
      } else if (error.code === error.TIMEOUT) {
        setFreshness('STALE');
        setErrorMessage('Location fix timed out. Retrying...');
      }
    };

    // Start watching position
    watchIdRef.current = navigator.geolocation.watchPosition(handleSuccess, handleError, {
      enableHighAccuracy: true,
      maximumAge: 10000,
      timeout: 20000,
    });

    return () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
      setIsTracking(false);
    };
  }, [enabled, sendLocationToBackend]);

  const requestPermission = useCallback(() => {
    if (!('geolocation' in navigator)) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        if (manualOverrideRef.current) return;
        setCoordinates({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        });
        setLastUpdated(new Date(pos.timestamp));
        setFreshness('LIVE');
        setPermissionState('granted');
        setErrorMessage(null);
        sendLocationToBackend(
          pos.coords.latitude,
          pos.coords.longitude,
          new Date(pos.timestamp).toISOString(),
        );
      },
      (err) => {
        if (manualOverrideRef.current) return;
        if (err.code === err.PERMISSION_DENIED) {
          setPermissionState('denied');
          setFreshness('UNAVAILABLE');
          setErrorMessage('Permission denied. Please allow location access in your browser.');
        }
      },
      { enableHighAccuracy: true, timeout: 15000 },
    );
  }, [sendLocationToBackend]);

  const setManualLocation = useCallback(
    async (lat: number, lon: number, label?: string) => {
      const overrideData: ManualLocationData = {
        latitude: lat,
        longitude: lon,
        label: label || 'Manual Calibration',
        timestamp: Date.now(),
      };
      try {
        localStorage.setItem(MANUAL_LOCATION_STORAGE_KEY, JSON.stringify(overrideData));
      } catch (err) {
        console.warn('Failed to save manual location to localStorage', err);
      }
      manualOverrideRef.current = overrideData;
      serverLocationRef.current = { latitude: lat, longitude: lon };
      setIsManualOverride(true);
      setManualLabel(overrideData.label || 'Manual');
      setCoordinates({ latitude: lat, longitude: lon, accuracy: 5 });
      setFreshness('LIVE');
      setPermissionState('granted');
      setLastUpdated(new Date(overrideData.timestamp));
      setErrorMessage(null);

      // Force push to backend immediately
      await sendLocationToBackend(lat, lon, new Date().toISOString(), true);

      // Broadcast event so all listening components update immediately
      window.dispatchEvent(
        new CustomEvent('fieldops:technician_location_updated', { detail: overrideData }),
      );
    },
    [sendLocationToBackend],
  );

  const clearManualOverride = useCallback(async () => {
    try {
      localStorage.removeItem(MANUAL_LOCATION_STORAGE_KEY);
    } catch {
      // Ignore
    }
    manualOverrideRef.current = null;
    serverLocationRef.current = null;
    setIsManualOverride(false);
    setManualLabel(null);

    window.dispatchEvent(
      new CustomEvent('fieldops:technician_location_updated', { detail: null }),
    );

    // Re-acquire genuine device hardware GPS
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const lat = pos.coords.latitude;
          const lon = pos.coords.longitude;
          setCoordinates({ latitude: lat, longitude: lon, accuracy: pos.coords.accuracy });
          setLastUpdated(new Date(pos.timestamp));
          setFreshness('LIVE');
          sendLocationToBackend(lat, lon, new Date(pos.timestamp).toISOString(), true);
        },
        (err) => {
          console.warn('[Geolocation] Re-acquire failed:', err.message);
        },
        { enableHighAccuracy: true, timeout: 15000 },
      );
    }
  }, [sendLocationToBackend]);

  return {
    coordinates,
    freshness,
    permissionState,
    lastUpdated,
    errorMessage,
    isTracking,
    requestPermission,
    isManualOverride,
    manualLabel,
    setManualLocation,
    clearManualOverride,
  };
}
