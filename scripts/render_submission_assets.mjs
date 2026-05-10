import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const __filename = fileURLToPath(import.meta.url);
const repoRoot = path.resolve(path.dirname(__filename), "..");
const submissionDir = path.join(repoRoot, "submission");
const require = createRequire(import.meta.url);
const { chromium } = require(path.join(repoRoot, "frontend/node_modules/playwright"));

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });

await page.goto(pathToFileURL(path.join(submissionDir, "cover.html")).href, { waitUntil: "networkidle" });
await page.screenshot({ path: path.join(submissionDir, "cover.png"), fullPage: false });

await page.goto(pathToFileURL(path.join(submissionDir, "deck.html")).href, { waitUntil: "networkidle" });
await page.pdf({
  path: path.join(submissionDir, "pitchsideai-deck.pdf"),
  printBackground: true,
  width: "1600px",
  height: "900px",
  margin: { top: "0", right: "0", bottom: "0", left: "0" },
  preferCSSPageSize: true
});

await browser.close();

console.log("Rendered submission/cover.png and submission/pitchsideai-deck.pdf");
