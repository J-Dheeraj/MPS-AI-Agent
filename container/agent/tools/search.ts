export async function searchKnowledge(query: string, mnemon: any): Promise<string> {
  const facts = mnemon.searchFacts(query);
  if (!facts.length) return 'No relevant information found in knowledge graph.';
  return facts.join('\n');
}
