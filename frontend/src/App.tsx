import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  ThemeProvider,
  CssBaseline,
  Grid,
  AppBar,
  Toolbar,
  Typography,
  Select,
  MenuItem,
  Button,
  Chip,
  Box,
} from '@mui/material';
import theme from './theme/theme';
import CameraFeed from './components/CameraFeed';
import DefectOverlay from './components/DefectOverlay';
import InspectionResults from './components/InspectionResults';
import ProxyMetrics from './components/ProxyMetrics';
import ProcessTrends from './components/ProcessTrends';
import ReportHistory from './components/ReportHistory';
import useWebSocket from './hooks/useWebSocket';
import { uploadImage, triggerInspection, getResults, listReports, getHealth } from './api';
import { InspectionResult, Report } from './types';

const App: React.FC = () => {
  const [result, setResult] = useState<InspectionResult | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [reports, setReports] = useState<Report[]>([]);
  const [trendData, setTrendData] = useState<{ timestamp: number; confidence: number; anomaly_rate: number }[]>([]);
  const [taskType, setTaskType] = useState<string>('defect_detection');
  const [health, setHealth] = useState<any>(null);

  const { connected, lastMessage } = useWebSocket('ws://localhost:8000/ws/stream');

  useEffect(() => {
    if (lastMessage && lastMessage.type === 'result') {
      setResult(lastMessage.data);
      setTrendData((prev) => [...prev, { timestamp: Date.now(), confidence: lastMessage.data.confidence, anomaly_rate: lastMessage.data.anomaly_rate }]);
    }
  }, [lastMessage]);

  useEffect(() => {
    listReports().then(setReports);
    getHealth().then(setHealth);
  }, []);

  const handleUpload = useCallback((file: File) => {
    setLoading(true);
    uploadImage(file, taskType).then((jobId) => {
      triggerInspection(taskType, 'camera').then(() => {
        getResults(jobId).then((resultData) => {
          setResult(resultData);
          setTrendData((prev) => [...prev, { timestamp: Date.now(), confidence: resultData.confidence, anomaly_rate: resultData.anomaly_rate }]);
          listReports().then(setReports);
          setLoading(false);
        });
      });
    });
  }, [taskType]);

  const handleTrigger = useCallback(() => {
    setLoading(true);
    triggerInspection(taskType, 'camera').then(() => {
      getResults('latest').then((resultData) => {
        setResult(resultData);
        setTrendData((prev) => [...prev, { timestamp: Date.now(), confidence: resultData.confidence, anomaly_rate: resultData.anomaly_rate }]);
        listReports().then(setReports);
        setLoading(false);
      });
    });
  }, [taskType]);

  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Vision_Inspect | Local Process Monitor
          </Typography>
          <Chip label={`WS ${connected ? 'Connected' : 'Disconnected'}`} color={connected ? 'success' : 'error'} />
          {health && <Chip label={`Ollama Status: ${health.status}`} />}
        </Toolbar>
      </AppBar>
      <Box p={2}>
        <Grid container spacing={2}>
          <Grid item xs={12} md={4}>
            <CameraFeed result={result} />
            {result && <DefectOverlay result={result} />}
          </Grid>
          <Grid item xs={12} md={4}>
            <Select value={taskType} onChange={(e) => setTaskType(e.target.value)} displayEmpty>
              <MenuItem value="">Select Task Type</MenuItem>
              <MenuItem value="defect_detection">Defect Detection</MenuItem>
              <MenuItem value="surface_anomaly_classification">Surface Anomaly Classification</MenuItem>
              <MenuItem value="nameplate_ocr">Nameplate OCR</MenuItem>
              <MenuItem value="serial_number_extraction">Serial Number Extraction</MenuItem>
              <MenuItem value="engineering_drawing_interpretation">Engineering Drawing Interpretation</MenuItem>
              <MenuItem value="process_deviation_flagging">Process Deviation Flagging</MenuItem>
            </Select>
            <Button variant="contained" onClick={handleTrigger} disabled={loading}>
              Trigger Inspection
            </Button>
            <input ref={fileInputRef} type="file" onChange={(e) => e.target.files && handleUpload(e.target.files[0])} style={{ display: 'none' }} />
            <Button variant="contained" component="label">
              Upload Image
              <input type="file" hidden accept="image/*" ref={fileInputRef} onChange={(e) => e.target.files && handleUpload(e.target.files[0])} />
            </Button>
            {result && <InspectionResults result={result} />}
            {result?.proxy_metrics && <ProxyMetrics proxyMetrics={result.proxy_metrics} />}
          </Grid>
          <Grid item xs={12} md={4}>
            <ProcessTrends trendData={trendData} />
            <ReportHistory reports={reports} />
          </Grid>
        </Grid>
      </Box>
    </ThemeProvider>
  );
};

export default App;
