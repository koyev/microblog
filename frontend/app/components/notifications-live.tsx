"use client";

import { useEffect, useState } from "react";

interface Notification {
  id?: number;
  message: string;
  live?: boolean;
}

export function NotificationsLive({
  initial,
}: {
  initial: Notification[];
}) {
  const [items, setItems] = useState<Notification[]>(initial);

  useEffect(() => {
    const es = new EventSource("/api/stream");

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as { connected?: boolean; message?: string };
        if (data.connected || !data.message) return;
        setItems((prev) => [{ message: data.message!, live: true }, ...prev]);
      } catch {
        // ignore parse errors
      }
    };

    return () => es.close();
  }, []);

  if (items.length === 0) {
    return (
      <p className="text-sm text-zinc-400">
        No notifications yet. Create a post to generate one.
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {items.map((n, i) => (
        <li
          key={n.id ?? `live-${i}`}
          className={`p-3 rounded-lg border text-sm ${
            n.live
              ? "border-blue-300 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-700"
              : "border-zinc-200 bg-white dark:bg-zinc-800 dark:border-zinc-700"
          }`}
        >
          {n.message}
          {n.live && (
            <span className="ml-2 text-xs font-medium text-blue-500">
              live
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}
