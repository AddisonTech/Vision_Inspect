import React from 'react';
import { Card, CardContent, Typography, Chip, Stack } from '@mui/material';
import { ProxyMetrics as PM } from '../types';

interface Props {
  metrics?: PM;
}

const ProxyMetrics: React.FC<Props> = ({ metrics }) => {
  if (!metrics) return null;

  const latencyColor = metrics.mean_latency_ms < 500 ? 'success' : metrics.mean_latency_ms < 2000 ? 'warning' : 'error';
  const confidenceColor = metrics.mean_confidence > 0.7 ? 'success' : metrics.mean_confidence > 0.4 ? 'warning' : 'error';
  const driftStatus = metrics.confidence_drift_alert ? 'ALERT' : 'OK';
  const shiftStatus = metrics.distribution_shift_alert ? 'ALERT' : 'OK';

  return (
    <Card>
      <CardContent>
        <Typography variant="h6">Proxy Metrics</Typography>
        <Stack direction="row" spacing={1}>
          <Chip label={`Latency: ${metrics.mean_latency_ms}ms`} color={latencyColor} />
          <Chip label={`Confidence: ${(metrics.mean_confidence * 100).toFixed(1)}%`} color={confidenceColor} />
          <Chip label={`Drift: ${driftStatus}`} color={driftStatus === 'ALERT' ? 'warning' : 'success'} />
          <Chip label={`Shift: ${shiftStatus}`} color={shiftStatus === 'ALERT' ? 'warning' : 'success'} />
        </Stack>
      </CardContent>
    </Card>
  );
};

export default ProxyMetrics;
