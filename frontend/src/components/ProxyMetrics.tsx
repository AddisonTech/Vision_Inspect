import React from 'react';
import { Card, CardContent, Typography, Chip, Stack } from '@mui/material';
import ProxyMetrics as PM from '../types';

interface Props {
  metrics?: PM;
}

const ProxyMetrics: React.FC<Props> = ({ metrics }) => {
  if (!metrics) return null;

  const latencyColor = metrics.latency < 500 ? 'success' : metrics.latency < 2000 ? 'warning' : 'error';
  const confidenceColor = metrics.confidence > 70 ? 'success' : metrics.confidence > 40 ? 'warning' : 'error';
  const driftStatus = metrics.drift ? 'ALERT' : 'OK';
  const shiftStatus = metrics.shift ? 'ALERT' : 'OK';

  return (
    <Card>
      <CardContent>
        <Typography variant="h6">Proxy Metrics</Typography>
        <Stack direction="row" spacing={1}>
          <Chip label={`Latency: ${metrics.latency}ms`} color={latencyColor} />
          <Chip label={`Confidence: ${metrics.confidence}%`} color={confidenceColor} />
          <Chip label={`Drift: ${driftStatus}`} color={driftStatus === 'ALERT' ? 'warning' : 'success'} />
          <Chip label={`Shift: ${shiftStatus}`} color={shiftStatus === 'ALERT' ? 'warning' : 'success'} />
        </Stack>
      </CardContent>
    </Card>
  );
};

export default ProxyMetrics;
