import type { VercelRequest, VercelResponse } from '@vercel/node';

// Types for Upstash (we'll use dynamic imports)
type UpstashRatelimit = any;
type UpstashRedis = any;

// Rate limiter instances (initialized lazily)
let redis: UpstashRedis | null = null;
let rateLimiters: Record<string, UpstashRatelimit | null> = {
  start: null,
  message: null,
  general: null,
};
let upstashInitialized = false;
let upstashAvailable = false;

// Initialize Upstash lazily (on first use)
async function initUpstash(): Promise<boolean> {
  if (upstashInitialized) return upstashAvailable;
  upstashInitialized = true;

  // Check if env vars are set
  const redisUrl = process.env.UPSTASH_REDIS_REST_URL?.trim();
  const redisToken = process.env.UPSTASH_REDIS_REST_TOKEN?.trim();

  if (!redisUrl || !redisToken) {
    console.log('[Rate Limiter] Upstash env vars not set, using in-memory fallback');
    return false;
  }

  try {
    // Dynamic imports
    const { Redis } = await import('@upstash/redis');
    const { Ratelimit } = await import('@upstash/ratelimit');

    redis = new Redis({
      url: redisUrl,
      token: redisToken,
    });

    rateLimiters = {
      start: new Ratelimit({
        redis,
        limiter: Ratelimit.slidingWindow(10, '1 m'),
        analytics: true,
        prefix: 'ratelimit:start',
      }),
      message: new Ratelimit({
        redis,
        limiter: Ratelimit.slidingWindow(30, '1 m'),
        analytics: true,
        prefix: 'ratelimit:message',
      }),
      general: new Ratelimit({
        redis,
        limiter: Ratelimit.slidingWindow(60, '1 m'),
        analytics: true,
        prefix: 'ratelimit:general',
      }),
    };

    upstashAvailable = true;
    console.log('[Rate Limiter] Upstash Redis initialized successfully');
    return true;
  } catch (error) {
    console.log('[Rate Limiter] Upstash not available, using in-memory fallback:', (error as Error).message);
    return false;
  }
}

// Fallback in-memory rate limiter
const inMemoryStore = new Map<string, { count: number; resetAt: number }>();

function cleanupExpired() {
  const now = Date.now();
  for (const [key, record] of Array.from(inMemoryStore.entries())) {
    if (record.resetAt < now) {
      inMemoryStore.delete(key);
    }
  }
}

function checkInMemoryLimit(key: string, limit: number, windowMs: number): { success: boolean; remaining: number; reset: number } {
  cleanupExpired();

  const now = Date.now();
  const record = inMemoryStore.get(key);

  if (!record || record.resetAt < now) {
    inMemoryStore.set(key, { count: 1, resetAt: now + windowMs });
    return { success: true, remaining: limit - 1, reset: now + windowMs };
  }

  if (record.count >= limit) {
    return { success: false, remaining: 0, reset: record.resetAt };
  }

  record.count++;
  return { success: true, remaining: limit - record.count, reset: record.resetAt };
}

export type RateLimitType = 'start' | 'message' | 'general';

const limits: Record<RateLimitType, { limit: number; windowMs: number }> = {
  start: { limit: 10, windowMs: 60000 },
  message: { limit: 30, windowMs: 60000 },
  general: { limit: 60, windowMs: 60000 },
};

export async function checkRateLimit(
  req: VercelRequest,
  res: VercelResponse,
  type: RateLimitType = 'general'
): Promise<boolean> {
  // Initialize Upstash on first call
  await initUpstash();

  // Get client IP
  const forwarded = req.headers['x-forwarded-for'];
  const ip = typeof forwarded === 'string'
    ? forwarded.split(',')[0].trim()
    : req.socket?.remoteAddress || 'unknown';

  const identifier = `${ip}:${type}`;
  const limiter = rateLimiters[type];
  const config = limits[type];

  let result: { success: boolean; remaining: number; reset: number };

  if (upstashAvailable && limiter) {
    // Use Upstash Redis rate limiter
    try {
      const upstashResult = await limiter.limit(identifier);
      result = {
        success: upstashResult.success,
        remaining: upstashResult.remaining,
        reset: upstashResult.reset,
      };
    } catch (error) {
      console.log('[Rate Limiter] Upstash error, falling back to in-memory:', (error as Error).message);
      result = checkInMemoryLimit(identifier, config.limit, config.windowMs);
    }
  } else {
    // Fallback to in-memory rate limiter
    result = checkInMemoryLimit(identifier, config.limit, config.windowMs);
  }

  // Set rate limit headers
  res.setHeader('X-RateLimit-Limit', config.limit);
  res.setHeader('X-RateLimit-Remaining', Math.max(0, result.remaining));
  res.setHeader('X-RateLimit-Reset', Math.ceil(result.reset / 1000));

  if (!result.success) {
    res.status(429).json({
      error: 'Too many requests',
      message: `Rate limit exceeded. Please try again in ${Math.ceil((result.reset - Date.now()) / 1000)} seconds.`,
      retryAfter: Math.ceil((result.reset - Date.now()) / 1000),
    });
    return false;
  }

  return true;
}

// Middleware wrapper for cleaner usage
export function withRateLimit(type: RateLimitType = 'general') {
  return async (
    req: VercelRequest,
    res: VercelResponse,
    handler: (req: VercelRequest, res: VercelResponse) => Promise<any>
  ) => {
    const allowed = await checkRateLimit(req, res, type);
    if (!allowed) return;
    return handler(req, res);
  };
}
