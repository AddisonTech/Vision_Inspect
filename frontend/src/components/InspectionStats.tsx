import React from 'react';
import { Card, CardContent, Typography, Box, Divider, LinearProgress } from '@mui/material';
import { InspectionStats as Stats } from '../types';

interface InspectionStatsProps {
  stats: Stats | null;
}

const StatRow: React.FC<{ label: string; value: string | number }> = ({ label, value }) => (
  <Box display="flex" justifyContent="space-between" py={0.25}>
    <Typography variant="body2" color="text.secondary">{label}</Typography>
    <Typography variant="body2" fontWeight={600}>{value}</Typography>
  </Box>
);

const InspectionStats: React.FC<InspectionStatsProps> = ({ stats }) => {
  if (!stats) return null;

  const passRate = stats.pass_rate ?? 0;
  const passColor = passRate >= 90 ? '#4caf50' : passRate >= 70 ? '#ff9800' : '#f44336';

  return (
    <Card sx={{ mb: 1 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>Inspection Stats</Typography>

        <StatRow label="Total inspections" value={stats.total} />
        <StatRow label="Today" value={stats.today} />
        <StatRow label="Pass rate" value={`${passRate}%`} />
        <Box mt={0.5} mb={1}>
          <LinearProgress
            variant="determinate"
            value={passRate}
            sx={{
              height: 6,
              borderRadius: 3,
              bgcolor: '#333',
              '& .MuiLinearProgress-bar': { bgcolor: passColor },
            }}
          />
        </Box>

        <Box display="flex" gap={2} mb={0.5}>
          <StatRow label="Pass" value={stats.passed ?? 0} />
          <StatRow label="Fail" value={stats.failed ?? 0} />
          <StatRow label="Review" value={stats.review ?? 0} />
        </Box>

        <Divider sx={{ my: 0.75 }} />
        <StatRow
          label="Avg confidence"
          value={stats.avg_confidence != null ? `${(stats.avg_confidence * 100).toFixed(1)}%` : '—'}
        />
        <StatRow
          label="Avg latency"
          value={stats.avg_latency_ms != null ? `${Math.round(stats.avg_latency_ms)} ms` : '—'}
        />
      </CardContent>
    </Card>
  );
};

export default InspectionStats;
