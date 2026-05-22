import { expect, Page, APIRequestContext } from '@playwright/test';

export async function loadFixture(
  request: APIRequestContext,
  fixture: string,
  step = 0
): Promise<Record<string, unknown>> {
  const response = await request.post('/test/load_fixture/', {
    data: { fixture, step }
  });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

export async function openSimulator(
  page: Page,
  uiMode: 'auto' | 'user'
): Promise<void> {
  await page.goto(`/simulator_home?ui_mode=${uiMode}&__test_backend_mode=${uiMode}`);
  await expect(page.locator('#game-container')).toBeVisible();
  await expect(page.locator('#game-container canvas').first()).toBeVisible();
}

export async function waitForDebugPopulation(
  page: Page,
  minimumPersonaCount: number
): Promise<void> {
  await page.waitForFunction(
    (expected) => {
      const debug = (window as any).__EDSIM_DEBUG__;
      return Boolean(
        debug &&
          Object.keys(debug.personas || {}).length >= expected &&
          Object.keys(debug.movement || {}).length >= expected
      );
    },
    minimumPersonaCount
  );
}

export async function waitForPersonaPopulation(
  page: Page,
  minimumPersonaCount: number
): Promise<void> {
  await page.waitForFunction(
    (expected) => {
      const debug = (window as any).__EDSIM_DEBUG__;
      return Boolean(
        debug &&
          Object.keys(debug.personas || {}).length >= expected
      );
    },
    minimumPersonaCount
  );
}

export async function readDebug(page: Page): Promise<any> {
  return page.evaluate(() => JSON.parse(JSON.stringify((window as any).__EDSIM_DEBUG__ || {})));
}
