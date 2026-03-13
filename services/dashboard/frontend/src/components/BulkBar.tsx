import { useState } from 'preact/hooks';
import { Box, Button, Group, Text, TextInput } from '@mantine/core';
import { IconCheck, IconTrash, IconUpload, IconX } from '@tabler/icons-react';

interface Props {
    count: number;
    onAssign: (name: string) => Promise<void>;
    onImport: () => Promise<void>;
    onDiscard: () => Promise<void>;
    onClear: () => void;
}

export function BulkBar({ count, onAssign, onImport, onDiscard, onClear }: Props) {
    const [name, setName] = useState('');
    const [busy, setBusy] = useState<string | null>(null);

    const run = async (key: string, fn: () => Promise<void>) => {
        setBusy(key);
        try { await fn(); } finally { setBusy(null); }
    };

    return (
        <Box
            style={{
                position: 'fixed',
                bottom: 0,
                left: 0,
                right: 0,
                zIndex: 200,
                background: 'var(--mantine-color-dark-7)',
                borderTop: '1px solid var(--mantine-color-dark-4)',
                padding: '10px 16px',
            }}
        >
            <Group justify="space-between" wrap="nowrap">
                <Group gap="xs">
                    <Text size="sm" fw={500}>{count} selezionate</Text>
                    <Button size="xs" variant="subtle" leftSection={<IconX size={12} />} onClick={onClear}>
                        Deseleziona
                    </Button>
                </Group>

                <Group gap="xs">
                    <TextInput
                        size="xs"
                        placeholder="Assegna nome..."
                        value={name}
                        onChange={(e: any) => setName((e.target as HTMLInputElement).value)}
                        style={{ width: 180 }}
                    />
                    <Button
                        size="xs"
                        leftSection={<IconCheck size={12} />}
                        disabled={!name.trim()}
                        loading={busy === 'assign'}
                        onClick={() => void run('assign', () => onAssign(name.trim()))}
                    >
                        Assegna
                    </Button>
                    <Button
                        size="xs"
                        color="blue"
                        leftSection={<IconUpload size={12} />}
                        loading={busy === 'import'}
                        onClick={() => void run('import', onImport)}
                    >
                        Importa
                    </Button>
                    <Button
                        size="xs"
                        color="red"
                        leftSection={<IconTrash size={12} />}
                        loading={busy === 'discard'}
                        onClick={() => void run('discard', onDiscard)}
                    >
                        Scarta
                    </Button>
                </Group>
            </Group>
        </Box>
    );
}
