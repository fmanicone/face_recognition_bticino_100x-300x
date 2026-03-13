import { Badge, Card, Checkbox, Group, Image, Stack, Text } from '@mantine/core';
import type { Face } from '../types';

const STATUS_COLOR: Record<string, string> = {
  pending: 'yellow',
  importing: 'blue',
  imported: 'green',
  discarded: 'red',
};

const FALLBACK =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' fill='%23444'/%3E%3C/svg%3E";

interface Props {
  face: Face;
  selected: boolean;
  onToggle: (id: number) => void;
  onDetail: (face: Face) => void;
}

export function FaceCard({ face, selected, onToggle, onDetail }: Props) {
  const label = face.assigned_name ?? face.suggested_name ?? '—';
  const score =
    face.suggested_score != null ? `${Math.round(face.suggested_score * 100)}%` : null;

  return (
    <Card
      shadow="sm"
      padding="xs"
      radius="md"
      withBorder
      style={{
        cursor: 'pointer',
        outline: selected ? '2px solid var(--mantine-color-blue-5)' : 'none',
        outlineOffset: 2,
      }}
    >
      <Card.Section onClick={() => onDetail(face)}>
        <Image
          src={`/api/faces/${face.id}/image`}
          height={140}
          fit="cover"
          fallbackSrc={FALLBACK}
        />
      </Card.Section>

      <Stack gap={4} mt={6}>
        <Group justify="space-between" align="center">
          <Checkbox
            size="xs"
            checked={selected}
            onChange={() => onToggle(face.id)}
            onClick={(e: MouseEvent) => e.stopPropagation()}
          />
          <Badge size="xs" color={STATUS_COLOR[face.status] ?? 'gray'}>
            {face.status}
          </Badge>
        </Group>
        <Text size="xs" truncate="end">{label}</Text>
        {score && <Text size="xs" c="dimmed">{score}</Text>}
      </Stack>
    </Card>
  );
}
