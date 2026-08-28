// hooks/useStream.ts — WS /api/stream (FINAL.md §10 "WebSocket"). Frozen envelope:
// { channel, sim_day, data }. Channels: event, decision, metrics, forecast, sim, log.
//
// This is the single websocket client for the dashboard — no second implementation. It only
// parses frames and dispatches to whichever handler the caller passed for that channel; it
// owns no application state itself.
//
// Reconnect: a dropped connection (server restart, network blip, backend redeploy) retries on
// a fixed delay rather than giving up. A snapshot (`sim`/`metrics`/`forecast`) is re-sent by
// the server on every connect (api/routers/events.py `_send_snapshot`), so a reconnect catches
// the UI back up on its own — callers don't need to do anything extra.
import { useEffect, useRef } from 'react';
import { API_BASE } from '../api/client';
import type {
  ComparisonMetrics,
  DecisionObject,
  Forecast,
  HelmEvent,
  SimStatus,
  StreamLogData,
} from '../types';

export interface StreamHandlers {
  onSim?: (data: SimStatus) => void;
  onEvent?: (data: HelmEvent) => void;
  onDecision?: (data: DecisionObject) => void;
  onMetrics?: (data: ComparisonMetrics) => void;
  onForecast?: (data: Forecast) => void;
  onLog?: (data: StreamLogData) => void;
}

const RECONNECT_DELAY_MS = 2000;

function wsUrl(): string {
  // API_BASE already includes /api (e.g. "http://localhost:8000/api") — swap the scheme and
  // append the route, same base VITE_API_BASE points the REST client at.
  return `${API_BASE.replace(/^http/, 'ws')}/stream`;
}

export function useStream(handlers: StreamHandlers, enabled = true): void {
  // Ref so a re-render with new handler closures doesn't tear down and reopen the socket —
  // only `enabled` flipping does that. Written in its own effect (not during render) so it
  // stays safe under concurrent rendering.
  const handlersRef = useRef(handlers);
  useEffect(() => {
    handlersRef.current = handlers;
  });

  useEffect(() => {
    if (!enabled) return undefined;

    let ws: WebSocket | null = null;
    let reconnectTimer: number | undefined;
    let cleanedUp = false;

    function connect() {
      ws = new WebSocket(wsUrl());

      ws.onmessage = (ev) => {
        let frame: { channel?: string; data?: unknown };
        try {
          frame = JSON.parse(ev.data as string);
        } catch {
          return; // malformed frame — never crash the UI (CLAUDE.md rule 9)
        }
        const h = handlersRef.current;
        switch (frame.channel) {
          case 'sim':
            h.onSim?.(frame.data as SimStatus);
            break;
          case 'event':
            h.onEvent?.(frame.data as HelmEvent);
            break;
          case 'decision':
            h.onDecision?.(frame.data as DecisionObject);
            break;
          case 'metrics':
            h.onMetrics?.(frame.data as ComparisonMetrics);
            break;
          case 'forecast':
            h.onForecast?.(frame.data as Forecast);
            break;
          case 'log':
            h.onLog?.(frame.data as StreamLogData);
            break;
          default:
          // unknown channel — ignore rather than throw, the contract may grow one day
        }
      };

      ws.onclose = () => {
        if (cleanedUp) return;
        reconnectTimer = window.setTimeout(connect, RECONNECT_DELAY_MS);
      };
      // A socket error is always followed by a close event — just let onclose schedule the
      // reconnect rather than doing it twice.
      ws.onerror = () => {
        ws?.close();
      };
    }

    connect();

    return () => {
      cleanedUp = true;
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [enabled]);
}
