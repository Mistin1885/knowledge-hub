import { ApiError } from '../api/client';
import { pageApi } from '../api/endpoints';

export interface ImportResult {
  created: number;
  updated: number;
  skipped: number;
  folders: number;
  failed: number;
  warnings: string[];
}

export interface ImportProgress {
  completed: number;
  total: number;
  current: string;
  result: ImportResult;
}

export function importSummary(result: ImportResult): string {
  const parts = [
    `${result.created} created`,
    `${result.updated} updated`,
    `${result.skipped} skipped`,
  ];
  if (result.folders) parts.push(`${result.folders} folders created`);
  if (result.failed) parts.push(`${result.failed} failed`);
  if (result.warnings.length) parts.push(`${result.warnings.length} warnings`);
  return parts.join(', ');
}

const MD_RE = /\.(md|markdown)$/i;
const IGNORED_DIRS = new Set(['.git', '.obsidian', '.trash']);

function relativePath(file: File): string {
  return (file.webkitRelativePath || file.name).replace(/^[/\\]+/, '').replace(/\\/g, '/');
}

function shouldIgnore(path: string): boolean {
  return path.split('/').some((part) => IGNORED_DIRS.has(part.toLowerCase()));
}

/**
 * Import arbitrary files or a complete Obsidian Vault at stable relative paths.
 * Binary assets go first so Markdown image references can be resolved and
 * rewritten by the server. Requests are deliberately sequential: it gives the
 * UI honest per-file progress and prevents duplicate folder creation races.
 */
export async function importVaultFiles(
  workspaceId: string,
  files: File[],
  parentId: string | null = null,
  onProgress?: (progress: ImportProgress) => void,
): Promise<ImportResult> {
  const ignored = files.filter((file) => shouldIgnore(relativePath(file)));
  const candidates = files.filter((file) => !shouldIgnore(relativePath(file)));
  const items = candidates
    .map((file) => ({ file, path: relativePath(file) }))
    .sort((a, b) => {
      const aMd = MD_RE.test(a.path);
      const bMd = MD_RE.test(b.path);
      return Number(aMd) - Number(bMd) || a.path.localeCompare(b.path);
    });
  const result: ImportResult = {
    created: 0,
    updated: 0,
    skipped: ignored.length,
    folders: 0,
    failed: 0,
    warnings: ignored.length ? [`Ignored ${ignored.length} Vault settings/version-control files.`] : [],
  };

  onProgress?.({ completed: 0, total: items.length, current: '', result: { ...result } });
  for (let index = 0; index < items.length; index += 1) {
    const { file, path } = items[index];
    try {
      const imported = await pageApi.importItem(workspaceId, file, path, parentId);
      result[imported.action] += 1;
      result.folders += imported.folders_created;
      for (const warning of imported.warnings) {
        if (!result.warnings.includes(warning) && result.warnings.length < 50) {
          result.warnings.push(warning);
        }
      }
    } catch (error) {
      result.failed += 1;
      const detail = error instanceof ApiError ? error.detail : 'Unknown error';
      if (result.warnings.length < 50) result.warnings.push(`${path}: ${detail}`);
    }
    onProgress?.({
      completed: index + 1,
      total: items.length,
      current: path,
      result: { ...result, warnings: [...result.warnings] },
    });
  }
  return result;
}

// Backward-compatible export for existing callers while all import entry
// points now support Markdown, binary files and full Obsidian Vaults.
export const importMarkdownFiles = importVaultFiles;
