import axios, { AxiosInstance } from 'axios';
import { InspectionResult, Report, InspectionRecord, InspectionStats } from './types';

const client: AxiosInstance = axios.create({
  baseURL: '/',
});

export const uploadImage = async (file: File, taskType: string): Promise<InspectionResult> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('task_type', taskType);

  const response = await client.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
};

export const triggerInspection = async (taskType: string, source: string): Promise<any> => {
  const response = await client.post('/inspect', { task_type: taskType, source });
  return response.data;
};

export const getResults = async (jobId: string): Promise<any> => {
  const response = await client.get(`/results/${jobId}`);
  return response.data;
};

export const generateReport = async (jobId: string): Promise<any> => {
  const response = await client.post(`/report/${jobId}`);
  return response.data;
};

export const listReports = async (): Promise<Report[]> => {
  const response = await client.get('/reports');
  return response.data;
};

export const getHealth = async (): Promise<any> => {
  const response = await client.get('/health');
  return response.data;
};

export const listCameras = async (): Promise<any> => {
  const response = await client.get('/cameras');
  return response.data;
};

export const toggleCamera = async (): Promise<{ paused: boolean }> => {
  const response = await client.post('/cameras/toggle');
  return response.data;
};

export const selectCamera = async (deviceIndex: number, streamUrl: string = ''): Promise<any> => {
  const response = await client.post('/cameras/select', { device_index: deviceIndex, stream_url: streamUrl });
  return response.data;
};

export const listInspections = async (params?: {
  limit?: number;
  offset?: number;
  task_type?: string;
  pass_fail?: string;
  since?: string;
}): Promise<InspectionRecord[]> => {
  const response = await client.get('/inspections', { params });
  return response.data;
};

export const getStats = async (): Promise<InspectionStats> => {
  const response = await client.get('/inspections/stats');
  return response.data;
};
