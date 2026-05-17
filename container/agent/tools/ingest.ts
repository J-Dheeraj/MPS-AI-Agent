export async function ingestTool(url: string, mnemon: any): Promise<string> {
  try {
    const res = await fetch(url);
    const html = await res.text();
    // Naive text extraction — in production use a proper parser
    const text = html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 5000);
    const domain = new URL(url).hostname;

    mnemon.addFact(url, 'content', text.slice(0, 500), domain);
    mnemon.addFact(url, 'source', domain, 'system');
    mnemon.addFact(url, 'ingested_at', new Date().toISOString(), 'system');

    return `Ingested ${url} — extracted ${text.length} characters and added to knowledge graph.`;
  } catch (err: any) {
    return `Failed to ingest ${url}: ${err.message}`;
  }
}
