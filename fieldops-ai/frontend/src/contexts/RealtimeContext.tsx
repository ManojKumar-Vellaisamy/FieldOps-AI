import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { env } from '@/config/env';
import type {
  OperationalEventType,
  RealtimeConnectionStatus,
  RealtimeEvent,
  RealtimeEventHandler,
} from '@/types/realtime.types';

interface RealtimeContextType {
  status: RealtimeConnectionStatus;
  lastEvent: RealtimeEvent | null;
  subscribe: <T = any>(
    eventType: OperationalEventType | '*',
    handler: RealtimeEventHandler<T>,
  ) => () => void;
  onResync: (callback: () => void) => () => void;
  reconnect: () => void;
}

const RealtimeContext = createContext<RealtimeContextType | undefined>(undefined);

const getWebSocketUrl = (token: string): string => {
  const baseUrl = env.apiBaseUrl;
  let wsUrl = '';
  if (baseUrl.startsWith('http://') || baseUrl.startsWith('https://')) {
    wsUrl = baseUrl.replace(/^http/, 'ws');
  } else {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    wsUrl = `${protocol}//${window.location.host}${baseUrl}`;
  }
  return `${wsUrl}/ws?token=${encodeURIComponent(token)}`;
};

export const RealtimeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, token } = useAuth();
  const [status, setStatus] = useState<RealtimeConnectionStatus>('DISCONNECTED');
  const [lastEvent, setLastEvent] = useState<RealtimeEvent | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectAttemptRef = useRef<number>(0);
  const handlersRef = useRef<Map<string, Set<RealtimeEventHandler>>>(new Map());
  const resyncCallbacksRef = useRef<Set<() => void>>(new Set());
  const isManuallyClosedRef = useRef<boolean>(false);
  const hasConnectedOnceRef = useRef<boolean>(false);

  const dispatchEvent = useCallback((event: RealtimeEvent) => {
    setLastEvent(event);

    // Specific handlers
    const specificHandlers = handlersRef.current.get(event.event);
    if (specificHandlers) {
      specificHandlers.forEach((handler) => {
        try {
          handler(event);
        } catch (err) {
          console.error(`[Realtime] Handler error for ${event.event}:`, err);
        }
      });
    }

    // Wildcard handlers
    const wildcardHandlers = handlersRef.current.get('*');
    if (wildcardHandlers) {
      wildcardHandlers.forEach((handler) => {
        try {
          handler(event);
        } catch (err) {
          console.error('[Realtime] Wildcard handler error:', err);
        }
      });
    }
  }, []);

  const triggerResync = useCallback(() => {
    console.info('[Realtime] Triggering authoritative state resync across active components.');
    resyncCallbacksRef.current.forEach((cb) => {
      try {
        cb();
      } catch (err) {
        console.error('[Realtime] Resync callback error:', err);
      }
    });
  }, []);

  const connect = useCallback(() => {
    if (!token || !user) {
      setStatus('DISCONNECTED');
      return;
    }

    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    const wsUrl = getWebSocketUrl(token);
    setStatus(hasConnectedOnceRef.current ? 'RECONNECTING' : 'CONNECTING');
    isManuallyClosedRef.current = false;

    try {
      const socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        console.info('[Realtime] WebSocket connection established successfully.');
        setStatus('CONNECTED');
        const wasReconnecting = hasConnectedOnceRef.current;
        hasConnectedOnceRef.current = true;
        reconnectAttemptRef.current = 0;

        // Start ping heartbeat
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'ping' }));
          }
        }, 25000);

        // If this was a reconnection after disconnect, trigger resync to catch missed events
        if (wasReconnecting) {
          triggerResync();
        }
      };

      socket.onmessage = (messageEvent) => {
        try {
          const payload = JSON.parse(messageEvent.data);
          if (payload.type === 'pong') {
            return;
          }
          if (payload.event) {
            dispatchEvent(payload as RealtimeEvent);
          }
        } catch (err) {
          console.warn('[Realtime] Non-JSON or malformed WebSocket message received:', messageEvent.data);
        }
      };

      socket.onerror = (error) => {
        console.warn('[Realtime] WebSocket error observed:', error);
      };

      socket.onclose = (event) => {
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        if (isManuallyClosedRef.current) {
          setStatus('DISCONNECTED');
          return;
        }

        // If closed with policy violation (1008), auth failed
        if (event.code === 1008) {
          console.warn('[Realtime] WebSocket closed by server with policy violation (auth expired/invalid).');
          setStatus('DISCONNECTED');
          return;
        }

        // Plan exponential backoff reconnect
        setStatus('RECONNECTING');
        const attempt = reconnectAttemptRef.current + 1;
        reconnectAttemptRef.current = attempt;
        const delay = Math.min(1000 * Math.pow(1.5, attempt), 15000);

        console.info(`[Realtime] Disconnected. Reconnecting in ${(delay / 1000).toFixed(1)}s (attempt ${attempt})...`);
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, delay);
      };
    } catch (err) {
      console.error('[Realtime] Failed to initialize WebSocket:', err);
      setStatus('DISCONNECTED');
    }
  }, [token, user, dispatchEvent, triggerResync]);

  const disconnect = useCallback(() => {
    isManuallyClosedRef.current = true;
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus('DISCONNECTED');
  }, []);

  const reconnect = useCallback(() => {
    disconnect();
    connect();
  }, [disconnect, connect]);

  useEffect(() => {
    if (token && user) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [token, user, connect, disconnect]);

  const subscribe = useCallback(<T = any>(
    eventType: OperationalEventType | '*',
    handler: RealtimeEventHandler<T>,
  ): (() => void) => {
    if (!handlersRef.current.has(eventType)) {
      handlersRef.current.set(eventType, new Set());
    }
    const set = handlersRef.current.get(eventType)!;
    set.add(handler as RealtimeEventHandler);

    return () => {
      set.delete(handler as RealtimeEventHandler);
      if (set.size === 0) {
        handlersRef.current.delete(eventType);
      }
    };
  }, []);

  const onResync = useCallback((callback: () => void): (() => void) => {
    resyncCallbacksRef.current.add(callback);
    return () => {
      resyncCallbacksRef.current.delete(callback);
    };
  }, []);

  return (
    <RealtimeContext.Provider
      value={{
        status,
        lastEvent,
        subscribe,
        onResync,
        reconnect,
      }}
    >
      {children}
    </RealtimeContext.Provider>
  );
};

export const useRealtime = (): RealtimeContextType => {
  const context = useContext(RealtimeContext);
  if (!context) {
    throw new Error('useRealtime must be used within a RealtimeProvider');
  }
  return context;
};
