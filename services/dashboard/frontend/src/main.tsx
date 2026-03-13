import { render } from 'preact';
import { MantineProvider, createTheme } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';
import { App } from './App';

const theme = createTheme({});

render(
  <MantineProvider theme={theme} defaultColorScheme="dark">
    <Notifications position="top-right" />
    <App />
  </MantineProvider>,
  document.getElementById('app')!,
);
