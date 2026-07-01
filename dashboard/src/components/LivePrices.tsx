"use client";

import { useEffect, useState } from "react";

interface LivePricesProps {
  children: (prices: Record<string, number>) => React.ReactNode;
}

export function LivePrices({ children }: LivePricesProps) {
  const [prices, setPrices] = useState<Record<string, number>>({});

  useEffect(() => {
    const fetchPrices = async () => {
      try {
        const res = await fetch("/api/prices", { cache: "no-store" });
        if (res.ok) {
          const data = await res.json();
          setPrices(data);
        }
      } catch {}
    };

    fetchPrices();
    const interval = setInterval(fetchPrices, 30000); // 30s
    return () => clearInterval(interval);
  }, []);

  return <>{children(prices)}</>;
}
