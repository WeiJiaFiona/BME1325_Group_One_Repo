import { expect, test } from '@playwright/test';
import { loadFixture, openSimulator, readDebug, waitForDebugPopulation } from './phaserTestUtils';

test('multi-role movement replays per-tile without avatar collisions', async ({ page, request }) => {
  await loadFixture(request, 'multi_role_paths');
  await openSimulator(page, 'user');
  await waitForDebugPopulation(page, 4);

  const debug = await readDebug(page);
  const movement = debug.movement || {};
  const personas = debug.personas || {};

  console.log({
    path_length: Object.fromEntries(Object.entries(movement).map(([name, data]: [string, any]) => [name, data.pathLength])),
    warning_count: Object.values(movement).filter((data: any) => data.warning).length,
    role_keys: Object.fromEntries(Object.entries(personas).map(([name, data]: [string, any]) => [name, data.roleKey])),
    avatar_keys: Object.fromEntries(Object.entries(personas).map(([name, data]: [string, any]) => [name, data.avatarKey]))
  });

  for (const data of Object.values(movement) as any[]) {
    expect(['movement_path', 'adjacent_fallback', 'stay_put']).toContain(data.source);
    expect(data.warning || '').not.toContain('missing_or_invalid_path');
    expect(data.queueLength).toBeGreaterThanOrEqual(0);
  }

  expect(personas['Doctor 1'].avatarKey).toBe('role_doctor');
  expect(personas['Patient 1'].avatarKey).toBe('role_patient');
  expect(personas['Doctor 1'].avatarKey).not.toBe(personas['Patient 1'].avatarKey);
  expect(debug.spawnOrder).toContain('Calling Nurse 1');
});
