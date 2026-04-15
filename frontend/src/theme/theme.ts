import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    mode: 'dark',
    background: {
      default: '#0d0d0d',
      paper: '#1a1a1a',
    },
    primary: {
      main: '#f59e0b', // amber — industrial warning color
    },
    secondary: {
      main: '#22d3ee', // cyan — data color
    },
    error: {
      main: '#ef4444',
    },
    success: {
      main: '#22c55e',
    },
    text: {
      primary: '#e5e7eb',
      secondary: '#9ca3af',
    },
  },
  typography: {
    fontFamily: 'JetBrains Mono, Consolas, monospace',
  },
});

export default theme;
