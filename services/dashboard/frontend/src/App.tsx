import { useCallback, useEffect, useState } from 'preact/hooks';
import {
  ActionIcon,
  AppShell,
  Burger,
  Group,
  Text,
  Title,
  Tooltip,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconRefresh } from '@tabler/icons-react';
import type { Face } from './types';
import * as api from './api';
import { Sidebar } from './components/Sidebar';
import { FaceGrid } from './components/FaceGrid';
import { BulkBar } from './components/BulkBar';
import { LiveModal } from './components/LiveModal';
import { FaceModal } from './components/FaceModal';

const PER_PAGE = 48;

export function App() {
  const [navOpen, { toggle: toggleNav }] = useDisclosure();
  const [faces, setFaces] = useState<Face[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [liveOpen, { open: openLive, close: closeLive }] = useDisclosure(false);
  const [detailFace, setDetailFace] = useState<Face | null>(null);

  const load = useCallback(async (s: string, q: string, p: number) => {
    setLoading(true);
    try {
      const data = await api.fetchFaces(s, q, p, PER_PAGE);
      setFaces(data.faces);
      setTotal(data.total);
      setTotalPages(Math.max(1, Math.ceil(data.total / PER_PAGE)));
      setSelected(new Set());
    } catch (e: unknown) {
      notifications.show({ color: 'red', message: String(e) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(status, search, page);
  }, [status, search, page, load]);

  const toggleSelect = (id: number) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    setSelected(selected.size === faces.length ? new Set() : new Set(faces.map(f => f.id)));
  };

  const withReload = (fn: () => Promise<void>) => async () => {
    try {
      await fn();
      void load(status, search, page);
    } catch (e: unknown) {
      notifications.show({ color: 'red', message: String(e) });
    }
  };

  const handleAssign = (name: string) =>
    withReload(async () => {
      await api.bulkAssign([...selected], name);
      notifications.show({ color: 'green', message: `Nome assegnato a ${selected.size} facce` });
    })();

  const handleImport = withReload(async () => {
    await api.bulkImport([...selected]);
    notifications.show({ color: 'blue', message: `Importazione avviata per ${selected.size} facce` });
  });

  const handleDiscard = withReload(async () => {
    await api.bulkDiscard([...selected]);
    notifications.show({ color: 'orange', message: `${selected.size} facce scartate` });
  });

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 260, breakpoint: 'sm', collapsed: { mobile: !navOpen } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger opened={navOpen} onClick={toggleNav} hiddenFrom="sm" size="sm" />
            <Title order={4}>Face Recognition Dashboard</Title>
          </Group>
          <Group gap="xs">
            <Text size="sm" c="dimmed">{total} facce</Text>
            <Tooltip label="Aggiorna">
              <ActionIcon variant="subtle" onClick={() => void load(status, search, page)} loading={loading}>
                <IconRefresh size={16} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        <Sidebar
          status={status}
          search={search}
          onStatusChange={(s) => { setStatus(s); setPage(1); }}
          onSearchChange={(q) => { setSearch(q); setPage(1); }}
          onOpenLive={openLive}
        />
      </AppShell.Navbar>

      <AppShell.Main>
        <FaceGrid
          faces={faces}
          loading={loading}
          selected={selected}
          onToggle={toggleSelect}
          onToggleAll={toggleAll}
          onDetail={setDetailFace}
          page={page}
          totalPages={totalPages}
          onPageChange={setPage}
        />
      </AppShell.Main>

      {selected.size > 0 && (
        <BulkBar
          count={selected.size}
          onAssign={handleAssign}
          onImport={handleImport}
          onDiscard={handleDiscard}
          onClear={() => setSelected(new Set())}
        />
      )}

      <LiveModal opened={liveOpen} onClose={closeLive} />
      <FaceModal face={detailFace} onClose={() => setDetailFace(null)} />
    </AppShell>
  );
}
