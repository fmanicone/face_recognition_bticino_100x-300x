import { useEffect, useState } from 'preact/hooks';
import {
  Box,
  Group,
  Image,
  SegmentedControl,
  Stack,
  Switch,
  Text,
  TextInput,
  UnstyledButton,
} from '@mantine/core';
import { useDebouncedCallback } from '@mantine/hooks';
import { IconSearch, IconDoorEnter } from '@tabler/icons-react';
import { fetchPersons, setAutoOpen } from '../api';

interface Props {
  status: string;
  search: string;
  onStatusChange: (s: string) => void;
  onSearchChange: (q: string) => void;
  onOpenLive: () => void;
}

export function Sidebar({ status, onStatusChange, onSearchChange, onOpenLive }: Props) {
  const [inputVal, setInputVal] = useState('');
  const [persons, setPersons] = useState<{ name: string; auto_open: number }[]>([]);
  const [knownNames, setKnownNames] = useState<string[]>([]);

  const debouncedSearch = useDebouncedCallback((value: string) => {
    onSearchChange(value);
  }, 400);

  const loadPersons = async () => {
    try {
      const data = await fetchPersons();
      setPersons(data.persons || []);
      setKnownNames(data.known_names || []);
    } catch {}
  };

  useEffect(() => { loadPersons(); }, []);

  const handleToggle = async (name: string, enabled: boolean) => {
    try {
      await setAutoOpen(name, enabled);
      await loadPersons();
    } catch {}
  };

  // Merge known names with persons data
  const personMap = new Map(persons.map(p => [p.name, p.auto_open]));
  const allNames = [...new Set([...knownNames, ...persons.map(p => p.name)])].sort();

  return (
    <Stack gap="md" h="100%">
      <TextInput
        leftSection={<IconSearch size={14} />}
        placeholder="Cerca nome..."
        value={inputVal}
        onChange={(e: any) => {
          const val = (e.target as HTMLInputElement).value;
          setInputVal(val);
          debouncedSearch(val);
        }}
      />

      <Box>
        <Text size="xs" c="dimmed" mb={6}>Stato</Text>
        <SegmentedControl
          fullWidth
          size="xs"
          value={status}
          onChange={onStatusChange}
          data={[
            { value: '', label: 'Tutti' },
            { value: 'pending', label: 'Pending' },
            { value: 'imported', label: 'Importati' },
            { value: 'discarded', label: 'Scartati' },
          ]}
        />
      </Box>

      <Box>
        <Group gap={6} mb={6}>
          <IconDoorEnter size={14} style={{ opacity: 0.5 }} />
          <Text size="xs" c="dimmed">Auto-apertura cancello</Text>
        </Group>
        <Stack gap={4}>
          {allNames.length === 0 ? (
            <Text size="xs" c="dimmed">Nessuna persona</Text>
          ) : (
            allNames.map(name => (
              <Group key={name} gap="xs" wrap="nowrap">
                <Switch
                  size="xs"
                  checked={!!personMap.get(name)}
                  onChange={(e: any) => handleToggle(name, e.currentTarget.checked)}
                />
                <Text size="xs" truncate style={{ flex: 1 }}>{name}</Text>
              </Group>
            ))
          )}
        </Stack>
      </Box>

      <Box mt="auto">
        <Text size="xs" c="dimmed" mb={6}>Camera live</Text>
        <UnstyledButton onClick={onOpenLive} style={{ display: 'block', width: '100%' }}>
          <Image
            src="/api/camera/latest"
            radius="md"
            fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 90'%3E%3Crect width='160' height='90' fill='%23333'/%3E%3Ctext x='80' y='50' text-anchor='middle' fill='%23888' font-size='11'%3ENo feed%3C/text%3E%3C/svg%3E"
            style={{ border: '1px solid var(--mantine-color-dark-4)', borderRadius: 8 }}
          />
        </UnstyledButton>
      </Box>
    </Stack>
  );
}
