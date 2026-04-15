import React from 'react';
import {
  Card, CardContent, Typography, List, ListItem, ListItemText,
  IconButton, Chip, Box,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import { InspectionRecord } from '../types';

interface ReportHistoryProps {
  inspections: InspectionRecord[];
  onDownload: (jobId: string) => void;
}

const passFailColor = (pf: string): 'success' | 'error' | 'warning' | 'default' => {
  switch (pf.toUpperCase()) {
    case 'PASS':   return 'success';
    case 'FAIL':   return 'error';
    case 'REVIEW': return 'warning';
    default:       return 'default';
  }
};

const taskLabel = (raw: string): string =>
  raw.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

const ReportHistory: React.FC<ReportHistoryProps> = ({ inspections, onDownload }) => {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>Inspection History</Typography>
        {inspections.length === 0 ? (
          <Typography variant="body2" color="text.secondary">No inspections yet.</Typography>
        ) : (
          <List dense disablePadding>
            {inspections.map((rec) => {
              const ts = new Date(rec.timestamp);
              const formatted = ts.toLocaleString(undefined, {
                month: 'short', day: 'numeric', year: 'numeric',
                hour: '2-digit', minute: '2-digit',
              });
              return (
                <ListItem
                  key={rec.job_id}
                  disableGutters
                  secondaryAction={
                    <IconButton
                      edge="end"
                      size="small"
                      color="secondary"
                      onClick={() => onDownload(rec.job_id)}
                      title="Download report"
                    >
                      <DownloadIcon fontSize="small" />
                    </IconButton>
                  }
                  sx={{ py: 0.5 }}
                >
                  <ListItemText
                    primary={
                      <Box display="flex" alignItems="center" gap={0.75} flexWrap="wrap">
                        <Chip
                          label={rec.pass_fail}
                          color={passFailColor(rec.pass_fail)}
                          size="small"
                          sx={{ fontWeight: 700, minWidth: 52 }}
                        />
                        <Typography variant="body2" component="span">
                          {taskLabel(rec.task_type)}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" component="span">
                          {(rec.confidence * 100).toFixed(0)}% conf
                        </Typography>
                      </Box>
                    }
                    secondary={
                      <Typography variant="caption" color="text.secondary">
                        {formatted} · {rec.finding_count} finding{rec.finding_count !== 1 ? 's' : ''} · {rec.job_id}
                      </Typography>
                    }
                  />
                </ListItem>
              );
            })}
          </List>
        )}
      </CardContent>
    </Card>
  );
};

export default ReportHistory;
