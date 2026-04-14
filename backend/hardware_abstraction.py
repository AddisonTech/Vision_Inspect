import os
import logging

def get_onnx_providers() -> list[str]:
    providers = []
    try:
        import onnxruntime.providers as ort_providers
        if 'CUDAExecutionProvider' in dir(ort_providers):
            providers.append('CUDAExecutionProvider')
        if 'OpenVINOExecutionProvider' in dir(ort_providers):
            providers.append('OpenVINOExecutionProvider')
    except ImportError:
        logging.warning("onnxruntime not installed, skipping provider checks")
    
    providers.append('CPUExecutionProvider')
    return providers

def get_device_info() -> dict:
    device_info = {
        'provider': get_onnx_providers()[0] if get_onnx_providers() else 'CPUExecutionProvider',
        'cuda_available': False,
        'cpu_count': os.cpu_count()
    }
    
    try:
        import torch
        device_info['cuda_available'] = torch.cuda.is_available()
    except ImportError:
        logging.warning("torch not installed, skipping CUDA availability check")
    
    return device_info
