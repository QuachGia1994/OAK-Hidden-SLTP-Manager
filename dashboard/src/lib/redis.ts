import { Redis } from "@upstash/redis";

export const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL || "",
  token: process.env.UPSTASH_REDIS_REST_TOKEN || "",
});

// Keys
export const KEYS = {
  signals: "sltp:signals",
  state: "sltp:state",
  news: "sltp:news",
  prices: "sltp:prices",
  factcheck: "sltp:factcheck",
};
