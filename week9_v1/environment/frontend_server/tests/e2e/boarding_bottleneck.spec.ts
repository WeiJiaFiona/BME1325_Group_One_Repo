import { expect, test } from '@playwright/test';
import { loadFixture, openSimulator, readDebug, waitForPersonaPopulation } from './phaserTestUtils';

test('boarding timeout and bottleneck scenario exposes runtime sync without replaying stale movement', async ({ page, request }) => {
  await loadFixture(request, 'boarding_bottleneck');
  await openSimulator(page, 'auto');
  await waitForPersonaPopulation(page, 4);

  const debug = await readDebug(page);
  const statusResponse = await request.get('/api/live_dashboard/');
  expect(statusResponse.ok()).toBeTruthy();
  const statusPayload = await statusResponse.json();

  console.log({
    boarding_resource_markers: statusPayload.resources || {},
    movement_sync_state: statusPayload.runtime_sync,
    render_step: debug.renderStep,
    playback_step: debug.playbackStep,
    movement_wait_reason: debug.movementWaitReason,
    initial_movement_consumed: debug.initialMovementConsumed,
    warning_count: Object.values(debug.movement || {}).filter((data: any) => data.warning).length
  });

  expect(statusPayload.runtime_sync.in_sync).toBeTruthy();
  expect((statusPayload.resources || {}).boarding_timeout_events).toBeGreaterThanOrEqual(1);
  expect((statusPayload.resources || {}).resource_bottleneck_events).toBeGreaterThanOrEqual(1);
  expect(debug.runtimeSync.latestMovementStep).toBe(statusPayload.runtime_sync.latest_movement_step);
  expect(debug.initialMovementConsumed).toBeFalsy();
  expect(debug.playbackStep).toBe(debug.renderStep + 1);
  expect(debug.movementWaitReason).not.toBe('environment_ahead_of_movement');
  for (const data of Object.values(debug.movement || {}) as any[]) {
    expect(data.source).not.toBe('snap_only');
  }
});
