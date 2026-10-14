// Diagnostic only: no schedule, Telegram token, stored state or paid services.
export async function probeSearch(query, fetchImpl = fetch, Rewriter = HTMLRewriter) {
  const url = `https://www.avito.ru/rossiya?${new URLSearchParams({ q: query, s: '104' })}`;
  const result = { query, status: null, cards: 0, listing_links: 0, samples: [],
    headings: [], queryFields: [], page_title: '', searchConfirmed: false, ready: false };
  let response;
  try {
    response = await fetchImpl(url, {
      headers: { 'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'ru-RU,ru;q=0.9' },
      redirect: 'follow', signal: AbortSignal.timeout(20000),
    });
  } catch {
    return { ...result, status: 'network_error' };
  }
  result.status = response.status;
  if (response.status !== 200) {
    await response.body?.cancel();
    return result;
  }
  let currentTitle = null;
  let currentHeading = null;
  const rewriter = new Rewriter()
    .on('[data-marker="item"]', { element() { result.cards++; } })
    .on('a[data-marker="item-title"]', {
      element(element) {
        result.listing_links++;
        currentTitle = { value: '' };
        if (result.samples.length < 8) result.samples.push(currentTitle);
        element.onEndTag(() => { currentTitle = null; });
      },
      text(chunk) { if (currentTitle) currentTitle.value += chunk.text; },
    })
    .on('title', { text(chunk) { result.page_title += chunk.text; } })
    .on('input[name="q"]', { element(element) { result.queryFields.push(element.getAttribute('value') || ''); } })
    .on('h1', {
      element(element) {
        currentHeading = { value: '' };
        result.headings.push(currentHeading);
        element.onEndTag(() => { currentHeading = null; });
      },
      text(chunk) { if (currentHeading) currentHeading.value += chunk.text; },
    });
  // Drain the transform so all streaming callbacks execute, without storing HTML.
  const reader = rewriter.transform(response).body.getReader();
  let bytes = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > 8_000_000) {
        await reader.cancel();
        return { ...result, ready: false, error: 'page_too_large' };
      }
    }
  } catch {
    return { ...result, ready: false, error: 'page_read_failed' };
  }
  result.samples = result.samples.map(value => value.value.trim());
  result.headings = result.headings.map(value => value.value.trim());
  result.page_title = result.page_title.trim();
  const wanted = query.toLowerCase();
  result.searchConfirmed = result.queryFields.some(value => value.toLowerCase() === wanted)
    || result.headings.some(value => value.toLowerCase().includes(wanted));
  result.ready = result.cards > 0 && result.listing_links > 0 && result.searchConfirmed;
  return result;
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method !== 'GET') return new Response('Method not allowed', { status: 405 });
    if (url.pathname !== '/' && url.pathname !== '/probe') return new Response('Not found', { status: 404 });
    const results = [];
    for (const query of ['Winx', 'Винкс']) results.push(await probeSearch(query));
    return Response.json({ ready: results.every(value => value.ready), results }, {
      headers: { 'Cache-Control': 'no-store' },
    });
  },
};
