import { Link } from 'react-router-dom';
import { useRelated } from '../../hooks/queries';
import { EmptyState, Spinner } from '../ui/primitives';

const REASON_STYLES: Record<string, string> = {
  links: 'bg-indigo-50 text-indigo-700',
  tags: 'bg-emerald-50 text-emerald-700',
  semantic: 'bg-amber-50 text-amber-700',
};

export default function RelatedTab({ pageId, slug }: { pageId: string; slug: string }) {
  const relatedQ = useRelated(pageId);

  if (relatedQ.isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }
  if (relatedQ.isError) return <EmptyState message="Could not load related pages." />;

  const related = relatedQ.data ?? [];
  if (related.length === 0) {
    return <EmptyState message="No related pages yet — add links and tags to find neighbors." />;
  }

  return (
    <div className="space-y-0.5">
      {related.map((r) => (
        <Link
          key={r.page.id}
          to={`/w/${slug}/p/${r.page.id}`}
          className="block rounded-md px-2 py-1.5 transition-colors duration-150 hover:bg-neutral-100"
        >
          <div className="flex items-center gap-2">
            <p className="min-w-0 flex-1 truncate text-[13px] font-medium text-neutral-800">
              {r.page.icon ? `${r.page.icon} ` : ''}
              {r.page.title || 'Untitled'}
            </p>
            <span className="flex-none text-[11px] tabular-nums text-neutral-400">
              {r.score.toFixed(2)}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap gap-1">
            {r.reasons.map((reason) => (
              <span
                key={reason}
                className={`rounded px-1.5 py-px text-[10px] font-medium ${
                  REASON_STYLES[reason] ?? 'bg-neutral-100 text-neutral-600'
                }`}
              >
                {reason}
              </span>
            ))}
          </div>
        </Link>
      ))}
    </div>
  );
}
