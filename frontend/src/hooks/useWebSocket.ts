import { useState, useEffect, useRef } from 'react';

const useWebSocket = (url: string) => {
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const webSocketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (webSocketRef.current) {
      webSocketRef.current.close();
    }

    webSocketRef.current = new WebSocket(url);

    webSocketRef.current.onopen = () => {
      setConnected(true);
      setError(null);
    };

    webSocketRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLastMessage(data);
      } catch (e) {
        setError('Error parsing message');
      }
    };

    webSocketRef.current.onerror = (error) => {
      setError(`WebSocket error: ${error.message}`);
    };

    webSocketRef.current.onclose = () => {
      setConnected(false);
      setTimeout(() => {
        useWebSocket(url); // Recreate the WebSocket instance
      }, 3000);
    };

    return () => {
      if (webSocketRef.current) {
        webSocketRef.current.close();
      }
    };
  }, [url]);

  return { connected, lastMessage, error };
};

export default useWebSocket;
