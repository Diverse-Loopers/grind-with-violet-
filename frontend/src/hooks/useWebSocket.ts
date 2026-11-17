"use client";

import { useEffect, useState, useRef } from "react";
import { WS_BASE } from "@/lib/constants";
import { ScannerInstrument } from "@/types";

export function useScannerWebSocket() {
  const [instruments, setInstruments] = useState<ScannerInstrument[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let reconnectTimeout: NodeJS.Timeout;

    function connect() {
      try {
        const ws = new WebSocket(`${WS_BASE}/ws/scanner`);
        wsRef.current = ws;

        ws.onopen = () => {
          setIsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "SCANNER_UPDATE" && Array.isArray(data.instruments)) {
              setInstruments(data.instruments);
            }
          } catch {
            // Ignore parse errors
          }
        };

        ws.onclose = () => {
          setIsConnected(false);
          reconnectTimeout = setTimeout(connect, 3000);
        };

        ws.onerror = () => {
          ws.close();
        };
      } catch {
        setIsConnected(false);
        reconnectTimeout = setTimeout(connect, 3000);
      }
    }

    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return { instruments, isConnected };
}
