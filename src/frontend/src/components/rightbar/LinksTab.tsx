import { Link } from 'react-router-dom';
import type { Page } from '../../api/types';
import { useBacklinks, usePageLinks, useUnlinkedMentions } from '../../hooks/queries';
import { EmptyState, Spinner } from '../ui/primitives';

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-1.5 mt-4 text-[11px] font-semibold uppercase tracking-wide text-neutral-400 first:mt-0">
      {children}
    </h3>
  );
}

function PageRow({ page, context, slug }: { page: Page; context?: string; slug: string }) {
  return (
    <Link
      to={`/w/${slug}/p/${page.id}`}
      className="block rounded-md px-2 py-1.5 transition-colors duration-150 hover:bg-neutral-100"
    >
      <p className="truncate text-[13px] font-medium text-neutral-800">
        {page.icon ? `${page.icon} ` : ''}
        {page.title || 'Untitled'}
      </p>
      {context && <p className="mt-0.5 line-clamp-2 text-xs text-neutral-500">{context}</p>}
    </Link>
  );
}

export default function LinksTab({ pageId, slug }: { pageId: string; slug: string }) {
  const backlinksQ = useBacklinks(pageId);
  const linksQ = usePageLinks(pageId);
  const mentionsQ = useUnlinkedMentions(pageId);

  if (backlinksQ.isLoading || linksQ.isLoading || mentionsQ.isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }
  if (backlinksQ.isError || linksQ.isError || mentionsQ.isError) {
    return <EmptyState message="Could not load link data." />;
  }

  const backlinks = backlinksQ.data ?? [];
  const outgoing = (linksQ.data?.outgoing ?? []).filter((l) => l.resolved && l.page);
  const unresolved = [
    ...(linksQ.data?.unresolved ?? []),
    ...(linksQ.data?.outgoing ?? []).filter((l) => !l.resolved),
  ];
  const mentions = mentionsQ.data ?? [];

  return (
    <div>
      <SectionTitle>Backlinks ({backlinks.length})</SectionTitle>
      {backlinks.length === 0 && <EmptyState message="No pages link here yet." />}
      {backlinks.map((b, i) => (
        <PageRow key={`${b.page.id}-${i}`} page={b.page} context={b.context} slug={slug} />
      ))}

      <SectionTitle>Outgoing links ({outgoing.length + unresolved.length})</SectionTitle>
      {outgoing.length === 0 && unresolved.length === 0 && (
        <EmptyState message="No outgoing links. Type [[ in the editor to add one." />
      )}
      {outgoing.map((l, i) => (
        <PageRow key={`${l.page!.id}-${i}`} page={l.page!} context={l.context} slug={slug} />
      ))}
      {unresolved.map((l, i) => (
        <div key={`unresolved-${i}`} className="rounded-md px-2 py-1.5">
          <p className="inline-flex items-center gap-1.5 text-[13px] font-medium text-amber-700">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
            {l.target_title}
            <span className="rounded bg-amber-50 px-1 py-px text-[10px] font-normal">
              unresolved
            </span>
          </p>
          {l.context && <p className="mt-0.5 line-clamp-2 text-xs text-neutral-500">{l.context}</p>}
        </div>
      ))}

      <SectionTitle>Unlinked mentions ({mentions.length})</SectionTitle>
      {mentions.length === 0 && <EmptyState message="No unlinked mentions of this title." />}
      {mentions.map((m, i) => (
        <PageRow key={`${m.page.id}-${i}`} page={m.page} context={m.context} slug={slug} />
      ))}
    </div>
  );
}
