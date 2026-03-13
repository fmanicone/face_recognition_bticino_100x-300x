import { Center, Checkbox, Group, Loader, Pagination, SimpleGrid, Text } from '@mantine/core';
import type { Face } from '../types';
import { FaceCard } from './FaceCard';

interface Props {
  faces: Face[];
  loading: boolean;
  selected: Set<number>;
  onToggle: (id: number) => void;
  onToggleAll: () => void;
  onDetail: (face: Face) => void;
  page: number;
  totalPages: number;
  onPageChange: (p: number) => void;
}

export function FaceGrid({
  faces,
  loading,
  selected,
  onToggle,
  onToggleAll,
  onDetail,
  page,
  totalPages,
  onPageChange,
}: Props) {
  if (loading) return <Center h={300}><Loader /></Center>;
  if (!faces.length) return <Center h={300}><Text c="dimmed">Nessuna faccia trovata</Text></Center>;

  const allSelected = faces.length > 0 && selected.size === faces.length;

  return (
    <>
      <Group mb="sm" gap="xs">
        <Checkbox
          size="xs"
          indeterminate={selected.size > 0 && !allSelected}
          checked={allSelected}
          onChange={onToggleAll}
        />
        <Text size="xs" c="dimmed">
          {selected.size > 0 ? `${selected.size} selezionate` : 'Seleziona tutto'}
        </Text>
      </Group>

      <SimpleGrid cols={{ base: 2, xs: 3, sm: 4, md: 5, lg: 6 }} spacing="xs">
        {faces.map(f => (
          <FaceCard
            key={f.id}
            face={f}
            selected={selected.has(f.id)}
            onToggle={onToggle}
            onDetail={onDetail}
          />
        ))}
      </SimpleGrid>

      {totalPages > 1 && (
        <Center mt="xl">
          <Pagination value={page} total={totalPages} onChange={onPageChange} size="sm" />
        </Center>
      )}
    </>
  );
}
