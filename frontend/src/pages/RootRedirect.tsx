import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useMe, useWorkspaces } from '../hooks/queries';
import { Button, Centered, ErrorNote, Spinner } from '../components/ui/primitives';
import CreateWorkspaceDialog from '../components/workspace/CreateWorkspaceDialog';

export default function RootRedirect() {
  const meQ = useMe();
  const workspacesQ = useWorkspaces();
  const [creating, setCreating] = useState(false);

  if (meQ.isLoading || workspacesQ.isLoading) {
    return (
      <Centered>
        <Spinner />
      </Centered>
    );
  }

  if (meQ.isError) return <Navigate to="/login" replace />;

  if (workspacesQ.isError) {
    return (
      <Centered>
        <ErrorNote message="Failed to load workspaces. Try reloading the page." />
      </Centered>
    );
  }

  const first = workspacesQ.data?.[0];
  if (first) return <Navigate to={`/w/${first.slug}`} replace />;

  return (
    <Centered>
      <div className="text-center">
        <h1 className="text-base font-semibold text-neutral-900">Welcome to Knowledge Map</h1>
        <p className="mt-1 text-[13px] text-neutral-500">
          You are not a member of any workspace yet.
        </p>
        <Button variant="primary" className="mt-4" onClick={() => setCreating(true)}>
          Create your first workspace
        </Button>
        {creating && <CreateWorkspaceDialog onClose={() => setCreating(false)} />}
      </div>
    </Centered>
  );
}
