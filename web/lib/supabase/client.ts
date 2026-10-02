import { createClient } from "@supabase/supabase-js";

export class SupabaseConfigurationError extends Error {}

// Initialize on demand so a missing local environment does not break the build.
export function createSupabaseClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim();
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim();

  if (!url || !key) {
    throw new SupabaseConfigurationError("Supabase public configuration is missing.");
  }

  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new SupabaseConfigurationError("Supabase URL is invalid.");
  }
  if (
    parsed.protocol !== "https:" || parsed.username || parsed.password ||
    parsed.search || parsed.hash || parsed.pathname !== "/"
  ) {
    throw new SupabaseConfigurationError("Use the team's HTTPS Supabase project URL.");
  }
  if (!/^sb_publishable_[A-Za-z0-9_-]+$/.test(key)) {
    throw new SupabaseConfigurationError("Use a Supabase publishable key.");
  }

  return createClient(url, key, {
    auth: {
      persistSession: false,
      autoRefreshToken: false,
      detectSessionInUrl: false,
    },
    global: {
      fetch: (input, init) => fetch(input, { ...init, cache: "no-store" }),
    },
  });
}
