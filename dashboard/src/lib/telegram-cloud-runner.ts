import "server-only";

import { executeClaimedCloudIntent, renderCloudExecutionResult } from "@/lib/telegram-cloud-execution";
import { claimCloudIntentExecution, finishCloudIntentExecution } from "@/lib/telegram-cloud-store";
import type { CloudIntent } from "@/lib/telegram-cloud-domain";

export async function runCloudIntentExecution(id: number, nowMs = Date.now()): Promise<CloudIntent | null> {
  const claim = await claimCloudIntentExecution(id, nowMs);
  if (!claim) return null;
  try {
    const outcome = await executeClaimedCloudIntent(claim.task);
    return finishCloudIntentExecution({
      task: claim.task,
      lockToken: claim.lockToken,
      status: outcome.status,
      results: outcome.results,
      error: outcome.error,
      nowMs: Date.now(),
    });
  } catch (error) {
    return finishCloudIntentExecution({
      task: claim.task,
      lockToken: claim.lockToken,
      status: "failed",
      error: error instanceof Error ? error.message : String(error),
      nowMs: Date.now(),
    });
  }
}

export { renderCloudExecutionResult };
