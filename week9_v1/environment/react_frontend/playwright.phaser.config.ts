import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: '../frontend_server/tests/e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: {
    baseURL: 'http://127.0.0.1:8010',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure'
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    }
  ],
  webServer: {
    command: 'python manage.py runserver 127.0.0.1:8010 --noreload',
    cwd: '../frontend_server',
    env: {
      ...process.env,
      EDSIM_TEST_MODE: '1',
      PYTHONUTF8: '1'
    },
    url: 'http://127.0.0.1:8010',
    reuseExistingServer: !process.env.CI,
    stdout: 'pipe',
    stderr: 'pipe',
    timeout: 90_000
  }
});
