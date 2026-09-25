import { defineConfig, devices } from '@playwright/test';

// Dedicated port and no server reuse avoid testing a different local checkout.
const baseURL = 'http://127.0.0.1:3100';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL, trace: 'retain-on-failure', screenshot: 'only-on-failure', serviceWorkers: 'block' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run start -- --port 3100',
    url: baseURL,
    reuseExistingServer: false,
    timeout: 60_000,
    env: { BETTER_AUTH_URL: baseURL, BETTER_AUTH_SECRET: 'test-only-auth-secret-for-browser-suite' },
  },
});
