import React from 'react';
import { Card, CardContent, Typography } from '@mui/material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface DataPoint {
  timestamp: string;
  confidence: number;
  anomaly_rate: number;
}

interface ProcessTrendsProps {
  data: DataPoint[];
}

const ProcessTrends: React.FC<ProcessTrendsProps> = ({ data }) => (
  <Card>
    <CardContent>
      <Typography variant="h5" component="div">
        Process Trends
      </Typography>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis dataKey="timestamp" tick={{ fill: '#9ca3af' }} />
          <YAxis type="number" domain={[0, 1]} yAxisId="left" />
          <YAxis type="number" domain={[0, 1]} yAxisId="right" orientation="right" />
          <Tooltip wrapperClassName="dark-tooltip" />
          <Legend />
          <Line
            type="monotone"
            dataKey="confidence"
            stroke="#22d3ee"
            yAxisId="left"
            dot={false}
          />
          <Line
            type="monotone"
            dataKey="anomaly_rate"
            stroke="#f59e0b"
            yAxisId="right"
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </CardContent>
  </Card>
);

export default ProcessTrends;
