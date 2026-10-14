import chromium from '@sparticuz/chromium';
import { chromium as playwright } from 'playwright-core';

export default async function handler(req, res) {
  let browser;
  try {
    browser = await playwright.launch({args: chromium.args, executablePath: await chromium.executablePath(), headless: true});
    const page = await browser.newPage({locale: 'ru-RU'});
    const query = req.query?.query === 'Винкс' ? 'Винкс' : 'Winx';
    const response = await page.goto(`https://www.avito.ru/rossiya?${new URLSearchParams({q: query, s: '104'})}`, {waitUntil: 'domcontentloaded', timeout: 25000});
    await page.locator('[data-marker="item"]').first().waitFor({timeout: 12000}).catch(() => {});
    const count = await page.locator('[data-marker="item"]').count();
    const samples = await page.locator('[data-marker="item-title"]').evaluateAll(nodes => nodes.slice(0, 8).map(n => n.textContent.trim()));
    const headings = await page.locator('h1').allTextContents();
    const queryFields = await page.locator('input[name="q"]').evaluateAll(nodes => nodes.map(n => n.value));
    const searchConfirmed = queryFields.some(value => value.toLowerCase() === query.toLowerCase()) || headings.some(value => value.toLowerCase().includes(query.toLowerCase()));
    const text = await page.locator('body').innerText({timeout: 3000});
    res.setHeader('Cache-Control', 'no-store');
    res.status(200).json({ready: count > 0 && searchConfirmed, searchConfirmed, query, status: response?.status(), cards: count, samples, headings, queryFields, url: page.url(), title: await page.title(), page_text: text.slice(0, 1600)});
  } catch (error) {
    console.error('Browser probe failed', error.message);
    res.status(502).json({ready: false, error: 'Browser probe failed'});
  } finally {
    await browser?.close();
  }
}
