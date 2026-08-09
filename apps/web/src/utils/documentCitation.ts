export type DocumentCitation = { documentId: string; sectionSlug: string };

export function parseCitation(sourceId: string): DocumentCitation | null {
  const parts = sourceId.split(":");
  if (parts.length !== 3 || !/^\d{3}$/.test(parts[2]) || !parts[0] || !parts[1]) return null;
  return { documentId: parts[0], sectionSlug: parts[1] };
}
