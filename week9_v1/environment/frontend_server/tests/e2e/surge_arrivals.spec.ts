import { expect, test } from '@playwright/test';
import { loadFixture, openSimulator, readDebug, waitForPersonaPopulation } from './phaserTestUtils';

test('surge arrivals load as a static environment snapshot before new movement arrives', async ({ page, request }) => {
  await loadFixture(request, 'surge_arrivals');
  await openSimulator(page, 'auto');
  await waitForPersonaPopulation(page, 8);

  const debug = await readDebug(page);
  const personas = debug.personas || {};
  const movement = debug.movement || {};
  const patientNames = Object.keys(personas).filter((name) => name.startsWith('Patient'));

  console.log({
    persona_count: Object.keys(personas).length,
    spawn_order: debug.spawnOrder,
    render_step: debug.renderStep,
    playback_step: debug.playbackStep,
    initial_movement_consumed: debug.initialMovementConsumed,
    runtime_sync: debug.runtimeSync,
    queue_saturation: Object.fromEntries(Object.entries(movement).map(([name, data]: [string, any]) => [name, data.queueLength])),
    warning_count: Object.values(movement).filter((data: any) => data.warning).length
  });

  expect(patientNames.length).toBeGreaterThanOrEqual(4);
  expect(debug.spawnOrder).toEqual(expect.arrayContaining(['Patient 1', 'Patient 2', 'Patient 3', 'Patient 4']));
  expect(personas['Doctor 1'].avatarKey).toBe('role_doctor');
  expect(personas['Triage Nurse 1'].avatarKey).toBe('role_triage_nurse');
  expect(debug.initialMovementConsumed).toBeFalsy();
  expect(debug.playbackStep).toBe(debug.renderStep + 1);
  expect(Object.keys(movement).length).toBe(0);
});
