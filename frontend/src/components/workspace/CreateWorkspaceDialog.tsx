import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreateWorkspace } from '../../hooks/mutations';
import { ApiError } from '../../api/client';
import { Modal } from '../ui/Modal';
import { Button, ErrorNote, Input, Label } from '../ui/primitives';

export default function CreateWorkspaceDialog({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [description, setDescription] = useState('');
  const [icon, setIcon] = useState('');
  const [error, setError] = useState<string | null>(null);
  const create = useCreateWorkspace();
  const navigate = useNavigate();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setError(null);
    create.mutate(
      {
        name: name.trim(),
        ...(slug.trim() ? { slug: slug.trim() } : {}),
        ...(description.trim() ? { description: description.trim() } : {}),
        ...(icon.trim() ? { icon: icon.trim() } : {}),
      },
      {
        onSuccess: (workspace) => {
          onClose();
          navigate(`/w/${workspace.slug}`);
        },
        onError: (err) =>
          setError(err instanceof ApiError ? err.detail : 'Failed to create workspace'),
      },
    );
  };

  return (
    <Modal title="New workspace" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        <div>
          <Label>Name</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </div>
        <div>
          <Label>Slug (optional)</Label>
          <Input
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="my-workspace"
          />
        </div>
        <div>
          <Label>Description (optional)</Label>
          <Input value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <div>
          <Label>Icon (optional)</Label>
          <Input value={icon} onChange={(e) => setIcon(e.target.value)} placeholder="🗂️" />
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" busy={create.isPending} disabled={!name.trim()}>
            Create workspace
          </Button>
        </div>
      </form>
    </Modal>
  );
}
