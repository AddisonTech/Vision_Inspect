import { useState, useEffect, useRef } from 'react';

const useWebSocket = (url: string) => {
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [reconnectTrigger, setReconnectTrigger] = useState(0);
  const webSocketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let intentionallyClosed = false;

    // Tear down the previous socket without triggering its reconnect logic.
    if (webSocketRef.current) {
      webSocketRef.current.onclose = null;
      webSocketRef.current.close();
    }

    const ws = new WebSocket(url);
    webSocketRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setError(null);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLastMessage(data);
      } catch (e) {
        setError('Error parsing message');
      }
    };

    ws.onerror = () => {
      setError('WebSocket error');
    };

    ws.onclose = () => {
      if (intentionallyClosed) return;
      setConnected(false);
      setTimeout(() => {
        setReconnectTrigger((n) => n + 1);
      }, 3000);
    };

    return () => {
      intentionallyClosed = true;
      ws.close();
    };
  }, [url, reconnectTrigger]);

  return { connected, lastMessage, error };
};

export default useWebSocket;
