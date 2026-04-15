import React from 'react';
import { Card, CardContent, Typography, List, ListItem, ListItemText, IconButton } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import { Report } from '../types';

interface ReportHistoryProps {
  reports: Report[];
  onDownload: (filename: string) => void;
}

const ReportHistory: React.FC<ReportHistoryProps> = ({ reports, onDownload }) => {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6">Report History</Typography>
        {reports.length === 0 ? (
          <Typography>No reports yet.</Typography>
        ) : (
          <List dense>
            {reports.map((report) => (
              <ListItem key={report.filename}>
                <ListItemText primary={report.filename} secondary={`${(report.size_bytes / 1024).toFixed(1)} KB`} />
                <IconButton color="secondary" onClick={() => onDownload(report.filename)}>
                  <DownloadIcon />
                </IconButton>
              </ListItem>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );
};

export default ReportHistory;
