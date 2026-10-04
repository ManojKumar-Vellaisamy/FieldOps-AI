import { useEffect, useRef } from 'react';
import { useRealtime } from '@/contexts/RealtimeContext';
import type { OperationalEventType, RealtimeEvent } from '@/types/realtime.types';

/**
 * Convenient React hook to subscribe to one or more operational real-time events.
 * Automatically cleans up subscription when the component unmounts.
 * Uses refs to stabilize callbacks, preventing unnecessary re-subscriptions and effect loops.
 *
 * @param eventTypes Event type or array of event types to listen for.
 * @param onEvent Callback invoked when any of the matching events arrive.
 * @param onResync Optional callback invoked when the connection reconnects to refresh authoritative state.
 */
export function useRealtimeSync(
  eventTypes: OperationalEventType | OperationalEventType[] | '*',
  onEvent: (event: RealtimeEvent) => void,
  onResync?: () => void,
) {
  const { status, subscribe, onResync: registerResync, reconnect } = useRealtime();

  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const onResyncRef = useRef(onResync);
  onResyncRef.current = onResync;

  const eventTypesKey = Array.isArray(eventTypes) ? eventTypes.slice().sort().join(',') : eventTypes;

  useEffect(() => {
    const types = Array.isArray(eventTypes) ? eventTypes : [eventTypes];
    const handler = (event: RealtimeEvent) => {
      onEventRef.current(event);
    };

    const unsubs = types.map((t) => subscribe(t, handler));

    return () => {
      unsubs.forEach((unsub) => unsub());
    };
  }, [eventTypesKey, subscribe]);

  useEffect(() => {
    if (!onResync) return;
    const unsubResync = registerResync(() => {
      onResyncRef.current?.();
    });
    return () => {
      unsubResync();
    };
  }, [registerResync, Boolean(onResync)]);

  return { status, reconnect };
}
