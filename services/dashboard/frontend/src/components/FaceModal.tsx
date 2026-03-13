import { Badge, Group, Image, Modal, Stack, Text } from '@mantine/core';
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
  face: Face | null;
  onClose: () => void;
}

export function FaceModal({ face, onClose }: Props) {
  return (
    <Modal opened={face !== null} onClose={onClose} title="Dettaglio faccia" centered size="md">
      {face && (
        <>
          <Image
            src={`/api/faces/${face.id}/image`}
            fit="contain"
            mah={300}
            fallbackSrc={FALLBACK}
          />
          <Stack gap="xs" mt="md">
            <Group>
              <Text fw={500} size="sm">ID:</Text>
              <Text size="sm">{face.id}</Text>
            </Group>
            <Group>
              <Text fw={500} size="sm">Stato:</Text>
              <Badge size="sm" color={STATUS_COLOR[face.status] ?? 'gray'}>{face.status}</Badge>
            </Group>
            {face.suggested_name && (
              <Group>
                <Text fw={500} size="sm">Suggerito:</Text>
                <Text size="sm">
                  {face.suggested_name}
                  {face.suggested_score != null && ` (${Math.round(face.suggested_score * 100)}%)`}
                </Text>
              </Group>
            )}
            {face.assigned_name && (
              <Group>
                <Text fw={500} size="sm">Assegnato:</Text>
                <Text size="sm">{face.assigned_name}</Text>
              </Group>
            )}
            <Group>
              <Text fw={500} size="sm">Rilevato:</Text>
              <Text size="sm">{face.detected_at}</Text>
            </Group>
            <Group>
              <Text fw={500} size="sm">Sessione:</Text>
              <Text size="xs" truncate="end" style={{ maxWidth: 300 }}>{face.session_id}</Text>
            </Group>
          </Stack>
        </>
      )}
    </Modal>
  );
}
