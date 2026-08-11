import { createContext, useCallback, useContext, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { importVaultFiles, type ImportProgress, type ImportResult } from '../../lib/importMd';
import ImportStatus from '../sidebar/ImportStatus';

interface ImportManagerValue {
  isImporting: boolean;
  startImport: (
    workspaceId: string,
    files: File[],
    parentId?: string | null,
  ) => Promise<boolean>;
}

interface ImportJob {
  progress: ImportProgress | null;
  result: ImportResult | null;
  visible: boolean;
}

const ImportManagerContext = createContext<ImportManagerValue | null>(null);

export function ImportManagerProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const activeRef = useRef(false);
  const [isImporting, setIsImporting] = useState(false);
  const [job, setJob] = useState<ImportJob | null>(null);

  const startImport = useCallback(
    async (workspaceId: string, files: File[], parentId: string | null = null) => {
      if (files.length === 0) return false;
      if (activeRef.current) {
        setJob((current) => (current ? { ...current, visible: true } : current));
        return false;
      }

      activeRef.current = true;
      setIsImporting(true);
      setJob({ progress: null, result: null, visible: true });
      try {
        const result = await importVaultFiles(workspaceId, files, parentId, (progress) => {
          setJob((current) => ({
            progress,
            result: null,
            // Dismissing a running notification only hides the presentation;
            // it never cancels the import or its progress updates.
            visible: current?.visible ?? true,
          }));
        });
        // A hidden in-progress notification returns when the job finishes and
        // remains visible until the user explicitly dismisses it.
        setJob({ progress: null, result, visible: true });
        return true;
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unexpected import error';
        setJob({
          progress: null,
          result: {
            created: 0,
            updated: 0,
            skipped: 0,
            folders: 0,
            failed: files.length,
            warnings: [message],
          },
          visible: true,
        });
        return false;
      } finally {
        activeRef.current = false;
        setIsImporting(false);
        await Promise.all([
          qc.invalidateQueries({ queryKey: ['pages', workspaceId] }),
          qc.invalidateQueries({ queryKey: ['tags', workspaceId] }),
          qc.invalidateQueries({ queryKey: ['children'] }),
          qc.invalidateQueries({ queryKey: ['graph', workspaceId] }),
        ]);
      }
    },
    [qc],
  );

  return (
    <ImportManagerContext.Provider
      value={{ isImporting, startImport }}
    >
      {children}
      {job?.visible ? (
        <ImportStatus
          progress={job.progress}
          result={job.result}
          onClose={() => setJob((current) => (current ? { ...current, visible: false } : null))}
        />
      ) : null}
    </ImportManagerContext.Provider>
  );
}

export function useImportManager(): ImportManagerValue {
  const value = useContext(ImportManagerContext);
  if (!value) throw new Error('useImportManager must be used inside ImportManagerProvider');
  return value;
}
