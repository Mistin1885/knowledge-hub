import type { Page } from '../api/types';

export interface PageTreeNode {
  page: Page;
  children: PageTreeNode[];
}

/** Build a page tree from the flat list using parent_id + position. */
export function buildPageTree(pages: Page[]): PageTreeNode[] {
  const ids = new Set(pages.map((p) => p.id));
  const byParent = new Map<string | null, Page[]>();

  for (const page of pages) {
    // Pages whose parent is not visible to us are treated as roots.
    const key = page.parent_id !== null && ids.has(page.parent_id) ? page.parent_id : null;
    const list = byParent.get(key);
    if (list) list.push(page);
    else byParent.set(key, [page]);
  }

  for (const list of byParent.values()) {
    list.sort((a, b) => a.position - b.position || a.title.localeCompare(b.title));
  }

  const build = (parentId: string | null): PageTreeNode[] =>
    (byParent.get(parentId) ?? []).map((page) => ({
      page,
      children: build(page.id),
    }));

  return build(null);
}

/** Ancestor ids of a page (used to auto-expand the tree to the current page). */
export function ancestorIds(pages: Page[], pageId: string): string[] {
  const byId = new Map(pages.map((p) => [p.id, p]));
  const result: string[] = [];
  let current = byId.get(pageId);
  while (current && current.parent_id) {
    const parent = byId.get(current.parent_id);
    if (!parent || result.includes(parent.id)) break;
    result.push(parent.id);
    current = parent;
  }
  return result;
}
