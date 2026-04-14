import React from 'react';
import { InspectionResult } from '../types';
import {
  Card,
  CardContent,
  Typography,
  Chip,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Skeleton,
} from '@mui/material';

interface InspectionResultsProps {
  result?: InspectionResult;
  loading: boolean;
}

const InspectionResults: React.FC<InspectionResultsProps> = ({ result, loading }) => {
  if (loading) {
    return (
      <Card>
        <CardContent>
          <Skeleton height={200} />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h6">Inspection Results</Typography>
        {result ? (
          <>
            <Chip
              label={result.pass_fail}
              color={result.pass_fail === 'Pass' ? 'success' : 'error'}
              sx={{ mb: 1 }}
            />
            <Typography>{`Timestamp: ${new Date(result.timestamp).toLocaleString()}`}</Typography>
            <Typography>{`Model Used: ${result.model_used}`}</Typography>
            {result.findings.length > 0 && (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Label</TableCell>
                    <TableCell>Confidence</TableCell>
                    <TableCell>Severity</TableCell>
                    <TableCell>Description</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {result.findings.map((finding, index) => (
                    <TableRow key={index}>
                      <TableCell>{finding.label}</TableCell>
                      <TableCell>{finding.confidence.toFixed(2)}</TableCell>
                      <TableCell>{finding.severity}</TableCell>
                      <TableCell>{finding.description}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </>
        ) : (
          <Typography>No results yet.</Typography>
        )}
      </CardContent>
    </Card>
  );
};

export default InspectionResults;
