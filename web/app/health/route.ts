import {
  createSupabaseClient,
  SupabaseConfigurationError,
} from "@/lib/supabase/client";

function result(status: string, message: string, ok = false) {
  return Response.json(
    { ok, status, message },
    { status: ok ? 200 : 503, headers: { "Cache-Control": "no-store" } },
  );
}

export async function GET() {
  // Issue #7 owns the real schema and read permissions. Do not guess a table.
  const table = process.env.SUPABASE_HEALTH_TABLE?.trim();
  if (!table) {
    return result("blocked", "Configure a real HVAC table after Issue #7 is ready.");
  }
  if (!/^[a-z_][a-z0-9_]*$/.test(table)) {
    return result("configuration_error", "Configure an unqualified public table name.");
  }

  try {
    const supabase = createSupabaseClient();
    const { data, error } = await supabase
      .from(table)
      .select("*")
      .limit(1)
      .abortSignal(AbortSignal.timeout(10_000));

    if (error) {
      return result("read_failed", "HVAC read failed. Check schema, access, configuration, and connectivity.");
    }
    if (!data?.length) {
      return result("blocked", "No HVAC row is visible. Verify real data and read permissions with Issue #7.");
    }
    // Prove a row was read without returning HVAC data or database diagnostics.
    return result("ok", "Read one row from the configured HVAC table.", true);
  } catch (error) {
    if (error instanceof SupabaseConfigurationError) {
      return result("configuration_error", error.message);
    }
    return result("read_failed", "HVAC read could not complete.");
  }
}
