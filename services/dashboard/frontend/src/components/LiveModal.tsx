import { useCallback, useEffect, useState } from 'preact/hooks';
import { Image, Modal, Text } from '@mantine/core';

interface Props {
  opened: boolean;
  onClose: () => void;
}

export function LiveModal({ opened, onClose }: Props) {
  const [ts, setTs] = useState(Date.now());

  const tick = useCallback(() => setTs(Date.now()), []);

  useEffect(() => {
    if (!opened) return;
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [opened, tick]);

  return (
    <Modal opened={opened} onClose={onClose} title="Camera live" size="xl" centered>
      <Image
        src={`/api/camera/latest?t=${ts}`}
        fit="contain"
        fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 640 360'%3E%3Crect width='640' height='360' fill='%23333'/%3E%3Ctext x='320' y='190' text-anchor='middle' fill='%23888' font-size='20'%3ENo feed disponibile%3C/text%3E%3C/svg%3E"
      />
      <Text size="xs" c="dimmed" mt="sm" ta="center">Aggiornamento ogni secondo</Text>
    </Modal>
  );
}
