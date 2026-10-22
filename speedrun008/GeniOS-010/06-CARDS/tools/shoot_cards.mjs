// Render check of the Cards page (rohit/cards-ux) against the stand-in brain, signed in.
// Usage: node shoot_final.mjs <out-dir>   (dashboard on :3931, tools/mock_cards.py on :8031)
import { createRequire } from "module";
const require = createRequire(process.env.HOME + "/.claude/skills/gstack/node_modules/");
const { chromium } = require("playwright");
const BASE = "http://localhost:3931", OUT = process.argv[2];
const b = (s) => Buffer.from(JSON.stringify(s)).toString("base64url");
const token = `${b({ alg: "HS256" })}.${b({ sub: "p", email: "preview@example.com", exp: Math.floor(Date.now() / 1000) + 7200 })}.x`;
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = []; page.on("pageerror", (e) => errors.push(String(e)));
await page.goto(`${BASE}/auth/login`);
await page.evaluate((t) => { localStorage.setItem("genios_org_id", "org_preview"); localStorage.setItem("genios_user", JSON.stringify({ name: "Rohit", email: "preview@example.com" })); localStorage.setItem("genios_token", t); }, token);
await page.goto(`${BASE}/dashboard/cards`, { waitUntil: "networkidle" });
await page.waitForSelector("text=Confirm the call time with Evokoa", { timeout: 60000 });
await page.waitForTimeout(1500);
const shot = async (name) => { await page.waitForTimeout(700); await page.screenshot({ path: `${OUT}/${name}.png` }); };
await shot("cards-list");
const panel = page.locator('aside[aria-label="Card"]');
const body = panel.locator(".overflow-y-auto").first();
const open = async (id) => { await page.locator(`#card-${id}`).getByRole("button", { name: "Open", exact: true }).click(); await panel.waitFor(); };
const close = async () => { await page.keyboard.press("Escape"); await page.keyboard.press("Escape"); await page.waitForTimeout(300); };
const bottom = async () => { await body.evaluate((el) => el.scrollTo(0, el.scrollHeight)); };

await open("c-evokoa"); await shot("card-open-top");
await bottom(); await shot("card-open-bottom");
await panel.getByRole("button", { name: /Feedback/ }).click();
await panel.getByRole("button", { name: "A fact is wrong" }).click();
await panel.locator("input").first().fill("the call already happened on Monday");
await shot("card-feedback");
await panel.getByRole("button", { name: /Delegate/ }).click(); await page.waitForTimeout(800); await shot("card-delegate");
await panel.getByRole("button", { name: /Later/ }).click(); await shot("card-later");
await close();
await open("c-f24"); await shot("card-open-expert");
await close();
await open("c-f22"); await shot("card-open-question");
await close();
console.log(JSON.stringify({ errors }));
await browser.close();
