import { pageApi } from '../api/endpoints';

export interface ImportResult {
  pages: number;
  folders: number;
  skipped: number;
  failed: number;
}

const MD_RE = /\.(md|markdown)$/i;

/** Import .md files (optionally with directory structure from a folder pick)
 *  as workspace pages. Directories become folder pages; `Dir/Dir.md` becomes
 *  the folder's own notes so an exported zip round-trips cleanly. Non-md
 *  files are skipped. Wikilinks resolve server-side by title as pages land. */
export async function importMarkdownFiles(
  workspaceId: string,
  files: File[],
): Promise<ImportResult> {
  const mdFiles = files.filter((f) => MD_RE.test(f.name));
  const result: ImportResult = {
    pages: 0,
    folders: 0,
    skipped: files.length - mdFiles.length,
    failed: 0,
  };

  const folderIds = new Map<string, string>();
  const ensureFolder = async (dirPath: string): Promise<string | undefined> => {
    if (!dirPath) return undefined;
    const cached = folderIds.get(dirPath);
    if (cached) return cached;
    const parts = dirPath.split('/');
    const parentId = await ensureFolder(parts.slice(0, -1).join('/'));
    const created = await pageApi.create(workspaceId, {
      title: parts[parts.length - 1],
      parent_id: parentId,
      is_folder: true,
    });
    folderIds.set(dirPath, created.id);
    result.folders += 1;
    return created.id;
  };

  // Shallow paths first so parent folders exist before their contents.
  const items = mdFiles
    .map((file) => ({
      file,
      rel: (file.webkitRelativePath || file.name).replace(/^\/+/, ''),
    }))
    .sort(
      (a, b) => a.rel.split('/').length - b.rel.split('/').length || a.rel.localeCompare(b.rel),
    );

  for (const { file, rel } of items) {
    try {
      const content = await file.text();
      const parts = rel.split('/');
      const title = parts[parts.length - 1].replace(MD_RE, '').trim() || 'Untitled';
      const dirPath = parts.slice(0, -1).join('/');
      const dirName = parts.length > 1 ? parts[parts.length - 2] : '';
      const parentId = await ensureFolder(dirPath);
      if (parentId && title === dirName) {
        await pageApi.update(parentId, { content_md: content });
      } else {
        await pageApi.create(workspaceId, { title, parent_id: parentId, content_md: content });
        result.pages += 1;
      }
    } catch {
      result.failed += 1;
    }
  }
  return result;
}
