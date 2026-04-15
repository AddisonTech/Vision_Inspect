import React from 'react';
import { Box, Typography } from '@mui/material';
import { InspectionFinding } from '../types';

interface DefectOverlayProps {
  imageUrl: string;
  findings: InspectionFinding[];
}

const severityColorMap: { [key: string]: string } = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#22d3ee',
};

const DefectOverlay: React.FC<DefectOverlayProps> = ({ imageUrl, findings }) => (
  <Box sx={{ position: 'relative', width: '100%' }}>
    {imageUrl && (
      <Box
        component="img"
        src={imageUrl}
        alt="Inspection Image"
        sx={{ width: '100%', height: 'auto', display: 'block' }}
      />
    )}
    {findings.map((finding, idx) => {
      if (finding.bbox && finding.severity) {
        const [x1, y1, x2, y2] = finding.bbox;
        const severityColor = severityColorMap[finding.severity];
        return (
          <Box
            key={idx}
            sx={{
              position: 'absolute',
              top: `${y1}%`,
              left: `${x1}%`,
              width: `${x2 - x1}%`,
              height: `${y2 - y1}%`,
              border: `2px solid ${severityColor}`,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Typography
              variant="caption"
              color="white"
              sx={{
                backgroundColor: severityColor,
                padding: '2px 4px',
                borderRadius: '4px',
              }}
            >
              {finding.label} ({finding.confidence.toFixed(0)}%)
            </Typography>
          </Box>
        );
      }
      return null;
    })}
  </Box>
);

export default DefectOverlay;
