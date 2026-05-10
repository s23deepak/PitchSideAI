import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const require = createRequire(import.meta.url);
const { chromium } = require(path.join(root, 'frontend', 'node_modules', '@playwright', 'test'));
const outputDir = path.join(root, 'submission', 'recordings');
const videoPath = process.env.SUBMISSION_CLIP
  || path.join(root, 'test_images', 'YTDown_YouTube_INCREDIBLE-long-distance-goal-from-Furma_Media_MCVZURfXOC4_001_720p.mp4');
const baseUrl = process.env.SUBMISSION_APP_URL || 'http://localhost:5173';
const question = process.env.SUBMISSION_QUESTION || 'Why is that a foul?';
const seekSeconds = Number.parseFloat(process.env.SUBMISSION_SEEK_SECONDS || '5');

await fs.mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  deviceScaleFactor: 1,
  recordVideo: {
    dir: outputDir,
    size: { width: 1920, height: 1080 },
  },
});
const page = await context.newPage();
page.setDefaultTimeout(30_000);

const events = [];
page.on('console', (msg) => events.push(`[console:${msg.type()}] ${msg.text()}`));
page.on('pageerror', (err) => events.push(`[pageerror] ${err.message}`));
page.on('requestfailed', (req) => events.push(`[requestfailed] ${req.method()} ${req.url()} ${req.failure()?.errorText}`));

const step = async (name, fn) => {
  events.push(`[step] ${name}`);
  await fn();
  await page.screenshot({ path: path.join(outputDir, `${String(events.length).padStart(2, '0')}-${name.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}.png`), fullPage: false });
};

try {
  await step('open-fan-lens', async () => {
    await page.goto(`${baseUrl}/live?tab=fan-lens&home=Real%20Madrid&away=Barcelona&competition=El%20Clasico`, {
      waitUntil: 'networkidle',
    });
    await page.getByText('Upload your match footage').first().waitFor({ state: 'visible' });
  });

  await step('select-streamingvlm', async () => {
    await page.locator('select').first().selectOption('streaming_vlm');
  });

  await step('upload-video', async () => {
    const dropzones = page.locator('label.video-upload-dropzone');
    const count = await dropzones.count();
    let uploaded = false;
    for (let i = 0; i < count; i += 1) {
      const dropzone = dropzones.nth(i);
      if (await dropzone.isVisible()) {
        await dropzone.locator('input[type="file"]').setInputFiles(videoPath);
        uploaded = true;
        break;
      }
    }
    if (!uploaded) throw new Error('No visible Fan Lens video upload dropzone found');
    await page.getByRole('button', { name: /start (fan lens|video analysis)/i }).waitFor({ state: 'visible' });
    await page.waitForFunction(() => {
      const video = document.querySelector('video');
      return video && Number.isFinite(video.duration) && video.duration > 5;
    }, { timeout: 30_000 });
    await page.evaluate((seconds) => {
      const video = document.querySelector('video');
      if (video) {
        video.currentTime = seconds;
        video.pause();
      }
    }, seekSeconds);
  });

  await step('start-fan-lens', async () => {
    await page.getByRole('button', { name: /start (fan lens|video analysis)/i })
      .first()
      .evaluate((button) => button.click());
    await page.getByText(/Live|Reconnecting|frames/i).waitFor({ state: 'visible', timeout: 45_000 }).catch(() => {});
    await page.evaluate((seconds) => {
      const video = document.querySelector('video');
      if (video) video.currentTime = seconds;
    }, seekSeconds);
    await page.waitForTimeout(1_000);
  });

  await step('ask-text-question', async () => {
    await page.getByTestId('text-query-toggle').click();
    await page.getByTestId('text-query-input').fill(question);
    await page.getByTestId('text-query-submit').click();
    await page.locator('.split-screen').waitFor({ state: 'visible', timeout: 15_000 });
  });

  await step('wait-for-answer', async () => {
    await page.waitForFunction(() => {
      const panel = document.querySelector('.split-screen-right');
      const text = panel?.textContent || '';
      return /AI CLIP ANALYSIS/i.test(text)
        && !/Watching the current video moment|Analyzing clip/i.test(text)
        && text.trim().length > 80;
    }, { timeout: 180_000 }).catch(() => {});
    await page.waitForTimeout(8_000);
  });

  await page.screenshot({ path: path.join(outputDir, 'final-split-screen.png'), fullPage: false });
} finally {
  const video = page.video();
  await context.close();
  const rawVideoPath = video ? await video.path().catch(() => null) : null;
  await browser.close();

  const logPath = path.join(outputDir, 'fan-lens-recording-log.txt');
  const summary = [
    `App URL: ${baseUrl}`,
    `Clip: ${videoPath}`,
    `Seek seconds: ${seekSeconds}`,
    `Backend selected: StreamingVLM`,
    `Question: ${question}`,
    rawVideoPath ? `Recording: ${rawVideoPath}` : 'Recording: unavailable',
    '',
    ...events,
  ].join('\n');
  await fs.writeFile(logPath, summary, 'utf8');
  console.log(summary);
}
