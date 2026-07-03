import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useWorkspaceCtx } from '../components/layout/WorkspaceLayout';
import { useGraph } from '../hooks/queries';
import GraphCanvas from '../components/graph/GraphCanvas';
import { Centered, EmptyState, ErrorNote, Spinner } from '../components/ui/primitives';

export default function GraphPage() {
  const { workspace } = useWorkspaceCtx();
  const navigate = useNavigate();
  const [showTags, setShowTags] = useState(true);
  const graphQ = useGraph(workspace.id, showTags);

  if (graphQ.isLoading) {
    return (
      <Centered>
        <Spinner />
      </Centered>
    );
  }
  if (graphQ.isError || !graphQ.data) {
    return (
      <Centered>
        <ErrorNote message="Failed to load the graph." />
      </Centered>
    );
  }

  const data = graphQ.data;

  return (
    <div className="relative h-full">
      <div className="absolute left-3 top-3 z-10 flex items-center gap-3 rounded-md border border-neutral-200 bg-white px-3 py-1.5">
        <label className="flex cursor-pointer items-center gap-1.5 text-[13px] text-neutral-700">
          <input
            type="checkbox"
            checked={showTags}
            onChange={(e) => setShowTags(e.target.checked)}
            className="h-3.5 w-3.5 accent-indigo-600"
          />
          Show tags
        </label>
        <span className="text-xs text-neutral-400">
          {data.nodes.length} nodes · {data.edges.length} edges
        </span>
      </div>
      {data.nodes.length === 0 ? (
        <EmptyState message="Nothing to plot yet — create pages and link them with [[wikilinks]]." />
      ) : (
        <GraphCanvas
          data={data}
          onNodeClick={(node) => {
            if (node.is_tag) {
              navigate(`/w/${workspace.slug}/tags/${encodeURIComponent(node.title)}`);
            } else {
              navigate(`/w/${workspace.slug}/p/${node.id}`);
            }
          }}
        />
      )}
    </div>
  );
}
