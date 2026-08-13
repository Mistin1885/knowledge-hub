import { Download, File, FileArchive, FileCode2, FileImage, FileText } from 'lucide-react';
import type { PageDetail } from '../../api/types';
import { downloadFile, formatBytes, formatDateTime } from '../../lib/utils';
import { useRuntimeConfig } from '../../hooks/queries';

function FileGlyph({ page, size = 26 }: { page: PageDetail; size?: number }) {
  if (page.preview_kind === 'image') return <FileImage size={size} />;
  if (page.preview_kind === 'pdf') return <FileText size={size} />;
  if (page.content_type?.includes('zip') || page.content_type?.includes('compressed')) {
    return <FileArchive size={size} />;
  }
  if (page.content_type?.startsWith('text/') || page.content_type?.includes('json')) {
    return <FileCode2 size={size} />;
  }
  return <File size={size} />;
}

export default function FileView({ page }: { page: PageDetail }) {
  const configQ = useRuntimeConfig();
  const download = () => page.download_url && downloadFile(page.download_url);

  return (
    <div className="mt-5 animate-[fadeIn_180ms_ease-out]">
      {page.preview_kind === 'image' && page.preview_url ? (
        <div className="flex min-h-80 items-center justify-center overflow-hidden rounded-lg border border-neutral-200 bg-neutral-50 p-3">
          <img
            src={page.preview_url}
            alt={page.title}
            className="max-h-[68vh] max-w-full rounded object-contain shadow-sm"
          />
        </div>
      ) : page.preview_kind === 'pdf' && page.preview_url ? (
        <div className="h-[68vh] overflow-hidden rounded-lg border border-neutral-200 bg-neutral-100">
          <iframe src={page.preview_url} title={page.title} className="h-full w-full" />
        </div>
      ) : (
        <div className="flex min-h-64 flex-col items-center justify-center border-y border-neutral-200 py-12 text-center">
          <div className="text-neutral-300">
            <FileGlyph page={page} size={42} />
          </div>
          <p className="mt-4 text-sm font-medium text-neutral-800">No browser preview</p>
          <p className="mt-1 text-xs text-neutral-500">Download this file to open it locally.</p>
        </div>
      )}

      <div className="mt-4 flex items-center gap-4 border-t border-neutral-100 pt-4">
        <span className="text-neutral-400">
          <FileGlyph page={page} />
        </span>
        <dl className="grid min-w-0 flex-1 grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
          <dt className="text-neutral-400">Type</dt>
          <dd className="truncate text-neutral-700">{page.content_type || 'Unknown'}</dd>
          <dt className="text-neutral-400">Size</dt>
          <dd className="text-neutral-700">{formatBytes(page.size)}</dd>
          <dt className="text-neutral-400">Uploaded</dt>
          <dd className="text-neutral-700">{formatDateTime(page.created_at)}</dd>
        </dl>
        {configQ.data?.file_downloads_enabled && (
          <button
            onClick={download}
            disabled={!page.download_url}
            className="inline-flex flex-none items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-2 text-xs font-medium text-white transition-colors duration-150 hover:bg-indigo-700 disabled:opacity-50"
          >
            <Download size={14} /> Download
          </button>
        )}
      </div>
    </div>
  );
}
