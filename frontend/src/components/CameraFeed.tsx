import React, { useState, useRef } from 'react';
import {
  Card, CardContent, Typography, Button, Box, CircularProgress,
  IconButton, Popover, List, ListItemButton, ListItemText,
  Divider, TextField, Tooltip,
} from '@mui/material';
import VideocamIcon from '@mui/icons-material/Videocam';
import VideocamOffIcon from '@mui/icons-material/VideocamOff';
import SwitchVideoIcon from '@mui/icons-material/SwitchVideo';
import { listCameras, selectCamera, toggleCamera } from '../api';

interface Camera {
  device_index: number;
  label: string;
  stream_url: string;
  active: boolean;
}

interface CameraFeedProps {
  imageUrl?: string;
  streaming: boolean;
  onTrigger: () => void;
}

const CameraFeed: React.FC<CameraFeedProps> = ({ imageUrl, streaming, onTrigger }) => {
  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [rtspUrl, setRtspUrl] = useState('');
  const [switching, setSwitching] = useState(false);
  const [paused, setPaused] = useState(false);
  const [streamKey, setStreamKey] = useState(0); // bumped to force <img> reload
  const fileInputRef = useRef<HTMLInputElement>(null);

  const open = Boolean(anchorEl);

  const fetchCameras = () => {
    listCameras().then((data: any) => {
      setCameras(data.cameras || []);
      setPaused(data.paused ?? false);
      if (data.active?.stream_url) setRtspUrl(data.active.stream_url);
    });
  };

  const handleToggle = () => {
    setSwitching(true);
    toggleCamera().then((data) => {
      setPaused(data.paused);
      setStreamKey((k) => k + 1);
      setSwitching(false);
    });
  };

  const handleOpenSelector = (e: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(e.currentTarget);
    fetchCameras();
  };

  const handleClose = () => setAnchorEl(null);

  const handleSelectIndex = (idx: number) => {
    setSwitching(true);
    selectCamera(idx, '').then(() => {
      setStreamKey((k) => k + 1);
      setSwitching(false);
      handleClose();
    });
  };

  const handleApplyRtsp = () => {
    if (!rtspUrl.trim()) return;
    setSwitching(true);
    selectCamera(0, rtspUrl.trim()).then(() => {
      setStreamKey((k) => k + 1);
      setSwitching(false);
      handleClose();
    });
  };

  return (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
          <Typography variant="h6" color={paused ? 'text.secondary' : 'primary.main'}
            display="flex" alignItems="center" gap={0.5}>
            {paused ? <VideocamOffIcon fontSize="small" /> : <VideocamIcon fontSize="small" />}
            Live Feed
          </Typography>
          <Box display="flex" gap={0.5}>
            <Tooltip title={paused ? 'Turn camera on' : 'Turn camera off'}>
              <IconButton size="small" onClick={handleToggle} disabled={switching}
                color={paused ? 'default' : 'primary'}>
                {paused ? <VideocamOffIcon fontSize="small" /> : <VideocamIcon fontSize="small" />}
              </IconButton>
            </Tooltip>
            <Tooltip title="Switch camera">
              <span>
                <IconButton size="small" onClick={handleOpenSelector} disabled={switching || paused}>
                  <SwitchVideoIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          </Box>
        </Box>

        {/* Stream display */}
        <Box sx={{ bgcolor: '#000', minHeight: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
          {paused ? (
            <Box display="flex" flexDirection="column" alignItems="center" gap={1}>
              <VideocamOffIcon sx={{ fontSize: 48, color: '#444' }} />
              <Typography variant="body2" color="#555">Camera off</Typography>
            </Box>
          ) : imageUrl ? (
            <>
              <Box
                component="img"
                key={streamKey}
                src={`${imageUrl}${imageUrl.includes('?') ? '&' : '?'}t=${streamKey}`}
                alt="Live Feed"
                sx={{ maxWidth: '100%', maxHeight: '100%', display: 'block' }}
              />
              {streaming && (
                <CircularProgress size={32} color="secondary"
                  sx={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)' }} />
              )}
            </>
          ) : (
            streaming
              ? <CircularProgress size={40} color="secondary" />
              : <Typography variant="body2" color="text.secondary">No feed available</Typography>
          )}
        </Box>

        <Button variant="contained" color="primary" fullWidth onClick={onTrigger}
          disabled={streaming} sx={{ mt: 2 }}>
          {streaming ? 'Inspecting…' : 'Trigger Inspection'}
        </Button>

        {/* Camera selector popover */}
        <Popover open={open} anchorEl={anchorEl} onClose={handleClose}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}>
          <Box sx={{ width: 280, p: 1 }}>
            <Typography variant="caption" color="text.secondary" sx={{ px: 1 }}>
              USB / Built-in cameras
            </Typography>
            {cameras.length === 0 ? (
              <Typography variant="body2" sx={{ px: 1, py: 0.5, color: 'text.secondary' }}>
                Scanning…
              </Typography>
            ) : (
              <List dense disablePadding>
                {cameras.map((cam) => (
                  <ListItemButton
                    key={cam.device_index}
                    selected={cam.active}
                    onClick={() => handleSelectIndex(cam.device_index)}
                    disabled={switching}
                  >
                    <ListItemText
                      primary={cam.label}
                      secondary={cam.active ? 'Active' : undefined}
                    />
                  </ListItemButton>
                ))}
              </List>
            )}
            <Divider sx={{ my: 1 }} />
            <Typography variant="caption" color="text.secondary" sx={{ px: 1 }}>
              IP / RTSP stream
            </Typography>
            <Box sx={{ px: 1, pt: 0.5, pb: 1, display: 'flex', gap: 1 }}>
              <TextField
                size="small" fullWidth placeholder="rtsp://user:pass@192.168.1.x/stream"
                value={rtspUrl} onChange={(e) => setRtspUrl(e.target.value)}
              />
              <Button size="small" variant="outlined" onClick={handleApplyRtsp} disabled={switching || !rtspUrl.trim()}>
                Apply
              </Button>
            </Box>
          </Box>
        </Popover>
      </CardContent>
    </Card>
  );
};

export default CameraFeed;
