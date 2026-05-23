// Bug 1 fixed: SSRF — validate URL scheme and block private/internal hosts
// Bug 12 fixed: HTTP response size limited before loading into memory

const MAX_RESPONSE_BYTES = 2 * 1024 * 1024; // 2 MB cap

const BLOCKED_HOSTNAME = /^(localhost|host\.docker\.internal)$/i;

const PRIVATE_IP = /^(127\.|10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)/;

function validateIngestUrl(raw: string): string | null {
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    return 'invalid URL';
  }
  if (parsed.protocol !== 'https:') {
    return 'only https:// URLs are permitted';
  }
  if (BLOCKED_HOSTNAME.test(parsed.hostname)) {
    return `host "${parsed.hostname}" is not permitted`;
  }
  if (PRIVATE_IP.test(parsed.hostname)) {
    return `private IP range "${parsed.hostname}" is not permitted`;
  }
  return null; // valid
}

export async function ingestTool(url: string, mnemon: any): Promise<string> {
  const validationError = validateIngestUrl(url);
  if (validationError) {
    return `Ingestion blocked: ${validationError}.`;
  }

  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(15_000) });

    // Enforce response size limit — read incrementally, stop at cap
    const reader = res.body?.getReader();
    if (!reader) return `Failed to ingest ${url}: no response body.`;

    const chunks: Uint8Array[] = [];
    let totalBytes = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      totalBytes += value.byteLength;
      if (totalBytes > MAX_RESPONSE_BYTES) {
        reader.cancel();
        break; // truncate — don't reject, just use what we have
      }
      chunks.push(value);
    }

    const combined = new Uint8Array(totalBytes <= MAX_RESPONSE_BYTES ? totalBytes : MAX_RESPONSE_BYTES);
    let offset = 0;
    for (const chunk of chunks) {
      combined.set(chunk, offset);
      offset += chunk.byteLength;
    }
    const html = new TextDecoder().decode(combined);

    // Naive text extraction
    const text = html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    const excerpt = text.slice(0, 5000);
    const domain = new URL(url).hostname;

    mnemon.addFact(url, 'content', excerpt.slice(0, 500), domain);
    mnemon.addFact(url, 'source', domain, 'system');
    mnemon.addFact(url, 'ingested_at', new Date().toISOString(), 'system');

    return `Ingested ${url} — extracted ${text.length} characters (capped at ${MAX_RESPONSE_BYTES / 1024}KB) and added to knowledge graph.`;
  } catch (err: any) {
    return `Failed to ingest ${url}: ${err.message}`;
  }
}
