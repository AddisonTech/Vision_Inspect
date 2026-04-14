import React from 'react';
import { Card, CardContent, Typography, Button, Box, CircularProgress } from '@mui/material';
import VideocamIcon from '@mui/icons-material/Videocam';

interface CameraFeedProps {
  imageUrl?: string;
  streaming: boolean;
  onTrigger: () => void;
}

const CameraFeed: React.FC<CameraFeedProps> = ({ imageUrl, streaming, onTrigger }) => {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" color="primary.main">
          <VideocamIcon /> Live Feed
        </Typography>
        <Box sx={{ bgcolor: '#000', minHeight: '200px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {imageUrl ? (
            streaming ? (
              <>
                <img src={imageUrl} alt="Live Feed" style={{ maxWidth: '100%', maxHeight: '100%' }} />
                <CircularProgress size={40} color="secondary" style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }} />
              </>
            ) : (
              <img src={imageUrl} alt="Live Feed" style={{ maxWidth: '100%', maxHeight: '100%' }} />
            )
          ) : (
            streaming ? (
              <CircularProgress size={40} color="secondary" />
            ) : (
              <Typography variant="body2" color="text.secondary">
                No feed available
              </Typography>
            )
          )}
        </Box>
        <Button
          variant="contained"
          color="primary"
          fullWidth
          onClick={onTrigger}
          disabled={streaming}
          sx={{ mt: 2 }}
        >
          {streaming ? 'Inspecting...' : 'Trigger Inspection'}
        </Button>
      </CardContent>
    </Card>
  );
};

export default CameraFeed;
