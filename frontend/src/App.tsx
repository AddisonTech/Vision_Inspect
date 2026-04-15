import React, { useState, useEffect, useCallback } from 'react';
import {
  ThemeProvider,
  CssBaseline,
  Grid,
  AppBar,
  Toolbar,
  Typography,
  Select,
  MenuItem,
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
import { InspectionResult, Report, ProxyMetrics as PM } from './types';

const App: React.FC = () => {
  const [result, setResult] = useState<InspectionResult | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [reports, setReports] = useState<Report[]>([]);
  const [trendData, setTrendData] = useState<{ timestamp: string; confidence: number; anomaly_rate: number }[]>([]);
  const [taskType, setTaskType] = useState<string>('defect_detection');
  const [health, setHealth] = useState<any>(null);
  const [proxyMetrics, setProxyMetrics] = useState<PM | undefined>(undefined);

  const { connected, lastMessage } = useWebSocket('ws://localhost:8000/ws/stream');

  useEffect(() => {
    if (lastMessage && lastMessage.type === 'result') {
      setResult(lastMessage.data);
      setTrendData((prev) => [
        ...prev,
        {
          timestamp: new Date().toISOString(),
          confidence: lastMessage.data.confidence ?? 0,
          anomaly_rate: lastMessage.data.anomaly_rate ?? 0,
        },
      ]);
    }
    if (lastMessage && lastMessage.type === 'metrics') {
      setProxyMetrics(lastMessage.data);
    }
  }, [lastMessage]);

  useEffect(() => {
    listReports().then(setReports);
    getHealth().then(setHealth);
  }, []);

  const handleTrigger = useCallback(() => {
    setLoading(true);
    triggerInspection(taskType, 'camera')
      .then((resultData: any) => {
        setResult(resultData as InspectionResult);
        setTrendData((prev) => [
          ...prev,
          {
            timestamp: new Date().toISOString(),
            confidence: resultData.confidence ?? 0,
            anomaly_rate: resultData.findings?.length > 0 ? 1 : 0,
          },
        ]);
        return listReports();
      })
      .then(setReports)
      .finally(() => setLoading(false));
  }, [taskType]);

  const handleUpload = useCallback((file: File) => {
    setLoading(true);
    uploadImage(file, taskType)
      .then((uploadedResult) => {
        setResult(uploadedResult);
        return getResults(uploadedResult.job_id);
      })
      .then((resultData: InspectionResult) => {
        setResult(resultData);
        return listReports();
      })
      .then(setReports)
      .finally(() => setLoading(false));
  }, [taskType]);

  const handleDownload = useCallback((filename: string) => {
    window.open(`/api/report/${filename}`, '_blank');
  }, []);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Vision_Inspect | Local Process Monitor
          </Typography>
          <Chip label={`WS ${connected ? 'Connected' : 'Disconnected'}`} color={connected ? 'success' : 'error'} />
          {health && <Chip label={`Ollama: ${health.status}`} sx={{ ml: 1 }} />}
        </Toolbar>
      </AppBar>
      <Box p={2}>
        <Grid container spacing={2}>
          <Grid item xs={12} md={4}>
            <CameraFeed imageUrl="http://localhost:8000/stream" streaming={loading} onTrigger={handleTrigger} />
            {result && result.findings.length > 0 && <DefectOverlay imageUrl="" findings={result.findings} />}
          </Grid>
          <Grid item xs={12} md={4}>
            <Box mb={1}>
              <Select value={taskType} onChange={(e) => setTaskType(e.target.value)} displayEmpty fullWidth size="small">
                <MenuItem value="defect_detection">Defect Detection</MenuItem>
                <MenuItem value="surface_anomaly_classification">Surface Anomaly Classification</MenuItem>
                <MenuItem value="nameplate_ocr">Nameplate OCR</MenuItem>
                <MenuItem value="serial_number_extraction">Serial Number Extraction</MenuItem>
                <MenuItem value="engineering_drawing_interpretation">Engineering Drawing Interpretation</MenuItem>
                <MenuItem value="process_deviation_flagging">Process Deviation Flagging</MenuItem>
              </Select>
            </Box>
            <Box mb={1}>
              <label>
                <input type="file" hidden accept="image/*" onChange={(e) => e.target.files && handleUpload(e.target.files[0])} />
              </label>
            </Box>
            <InspectionResults result={result} loading={loading} />
            {proxyMetrics && <ProxyMetrics metrics={proxyMetrics} />}
          </Grid>
          <Grid item xs={12} md={4}>
            <ProcessTrends data={trendData} />
            <ReportHistory reports={reports} onDownload={handleDownload} />
          </Grid>
        </Grid>
      </Box>
    </ThemeProvider>
  );
};

export default App;
