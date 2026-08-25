import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const workspaceCss = readFileSync(resolve(process.cwd(), 'app/globals.css'), 'utf8')
  .replace("@import 'tailwindcss';", '');

test('long conversations scroll inside the workspace without moving its rails', async ({ page }) => {
  const messages = Array.from({ length: 36 }, (_, index) => `
    <article class="message ${index % 2 === 0 ? 'assistant' : 'user'}">
      <div class="message-author"><strong>${index % 2 === 0 ? 'Atlas' : 'You'}</strong></div>
      <div class="message-body">
        Message ${index + 1}: grounded answers stay readable while the conversation becomes longer.
      </div>
    </article>
  `).join('');

  await page.setContent(`
    <style>html, body { line-height: 1.5; } ${workspaceCss}</style>
    <main class="workspace-shell">
      <header class="mobile-header"><span>Atlas</span></header>
      <aside class="workspace-sidebar">
        <div class="sidebar-brand">Atlas</div>
        <button class="new-chat-button">New conversation</button>
        <nav class="workspace-nav"><button class="active">Ask Atlas</button></nav>
        <div class="conversation-heading">Conversations</div>
        <div class="conversation-list"><button class="active"><span>Long conversation</span></button></div>
        <div class="sidebar-account"><strong>Reader</strong></div>
      </aside>
      <section class="workspace-content">
        <header class="content-header"><div><small>Research workspace</small><h2>Long conversation</h2></div></header>
        <div class="chat-layout">
          <section class="message-column">
            <div class="messages">${messages}</div>
            <form class="composer"><textarea aria-label="Question"></textarea><div><span>Ask Atlas</span><button>Send</button></div></form>
          </section>
          <aside class="evidence-panel"><header><div><small>Evidence</small><h3>Sources</h3></div></header></aside>
        </div>
      </section>
    </main>
  `);

  const initial = await page.evaluate(() => {
    const shell = document.querySelector<HTMLElement>('.workspace-shell');
    const sidebar = document.querySelector<HTMLElement>('.workspace-sidebar');
    const messagesElement = document.querySelector<HTMLElement>('.messages');

    if (!shell || !sidebar || !messagesElement) throw new Error('Workspace fixture is incomplete.');

    return {
      documentHeight: document.scrollingElement?.scrollHeight ?? 0,
      viewportHeight: window.innerHeight,
      shellHeight: shell.getBoundingClientRect().height,
      sidebarTop: sidebar.getBoundingClientRect().top,
      sidebarHeight: sidebar.getBoundingClientRect().height,
      messageClientHeight: messagesElement.clientHeight,
      messageScrollHeight: messagesElement.scrollHeight,
      contentBottom: document.querySelector<HTMLElement>('.workspace-content')?.getBoundingClientRect().bottom ?? 0,
      composerBottom: document.querySelector<HTMLElement>('.composer')?.getBoundingClientRect().bottom ?? 0,
    };
  });

  expect(initial.documentHeight).toBeLessThanOrEqual(initial.viewportHeight + 1);
  expect(Math.abs(initial.shellHeight - initial.viewportHeight)).toBeLessThanOrEqual(1);
  expect(initial.messageScrollHeight).toBeGreaterThan(initial.messageClientHeight);
  expect(initial.composerBottom).toBeLessThanOrEqual(initial.contentBottom);

  await page.locator('.messages').evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });

  await expect.poll(() => page.locator('.messages').evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  expect(await page.evaluate(() => window.scrollY)).toBe(0);

  const viewport = page.viewportSize();
  if (viewport && viewport.width > 760) {
    const sidebarAfterScroll = await page.locator('.workspace-sidebar').boundingBox();
    expect(sidebarAfterScroll?.y).toBeCloseTo(initial.sidebarTop, 0);
    expect(sidebarAfterScroll?.height).toBeCloseTo(initial.sidebarHeight, 0);
    expect(sidebarAfterScroll?.y).toBeCloseTo(0, 0);
    expect(sidebarAfterScroll?.height).toBeCloseTo(viewport.height, 0);
  }

  if (viewport && viewport.width > 1020) {
    const evidence = await page.locator('.evidence-panel').boundingBox();
    const chat = await page.locator('.chat-layout').boundingBox();
    expect(evidence?.y).toBeCloseTo(chat?.y ?? 0, 0);
    expect(evidence?.height).toBeCloseTo(chat?.height ?? 0, 0);
  }
});
