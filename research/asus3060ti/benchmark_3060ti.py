"""CUDA/cuBLAS GEMM baseline on the exact RTX 3060 Ti; no device settings changed.

Uses existing Ollama CUDA libraries through their public C APIs. All output matrix
elements are checked against an all-ones reference. Independent child processes
run three trials. CUDA events measure GEMM only. This is a local protocol, not the
repository's compiled CUDA executable; compare only identical local protocols.
"""
import argparse
import ctypes as C
import datetime
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import numpy as np

HERE = Path(__file__).resolve().parent
LIBDIR = Path(os.environ['LOCALAPPDATA']) / 'Programs/Ollama/lib/ollama/cuda_v12'
SMI = Path(os.environ['SystemRoot']) / 'System32/nvidia-smi.exe'
MODES = [('fp32_pedantic', 0, None, 2), ('fp16_tensor_fp32_accumulate', 2, 68, 1),
         ('bf16_tensor_fp32_accumulate', 14, 68, 1), ('tf32_tensor_fp32_accumulate', 0, 77, 3)]

def telemetry():
    query = 'name,pci.bus_id,driver_version,utilization.gpu,memory.used,temperature.gpu,power.draw,power.limit,clocks.sm,clocks.mem'
    rows = subprocess.check_output([str(SMI), '--query-gpu=' + query, '--format=csv,noheader,nounits'], text=True).strip().splitlines()
    if len(rows) != 1:
        raise RuntimeError('Expected one NVIDIA GPU')
    fields = [f.strip() for f in rows[0].split(',')]
    if fields[0] != 'NVIDIA GeForce RTX 3060 Ti' or fields[1] != '00000000:01:00.0':
        raise RuntimeError('Unexpected NVIDIA GPU identity')
    return dict(zip(query.split(','), fields))

def bind(lib, name, args):
    func = getattr(lib, name)
    func.argtypes, func.restype = args, C.c_int
    def checked(*values):
        status = func(*values)
        if status:
            raise RuntimeError(f'{name} returned {status}')
    return checked

def trial(n, samples, warmup):
    dll_dir = os.add_dll_directory(str(LIBDIR))
    rt = C.CDLL(str(LIBDIR / 'cudart64_12.dll'))
    bl = C.CDLL(str(LIBDIR / 'cublas64_12.dll'))
    ptr, integer, size = C.c_void_p, C.c_int, C.c_size_t
    select = bind(rt, 'cudaDeviceGetByPCIBusId', [C.POINTER(integer), C.c_char_p])
    device = integer()
    select(C.byref(device), b'0000:01:00.0')
    bind(rt, 'cudaSetDevice', [integer])(device)
    malloc = bind(rt, 'cudaMalloc', [C.POINTER(ptr), size])
    free = bind(rt, 'cudaFree', [ptr])
    transfer = bind(rt, 'cudaMemcpy', [ptr, ptr, size, integer])
    sync = bind(rt, 'cudaDeviceSynchronize', [])
    event_create = bind(rt, 'cudaEventCreate', [C.POINTER(ptr)])
    event_record = bind(rt, 'cudaEventRecord', [ptr, ptr])
    event_sync = bind(rt, 'cudaEventSynchronize', [ptr])
    event_ms = bind(rt, 'cudaEventElapsedTime', [C.POINTER(C.c_float), ptr, ptr])
    event_destroy = bind(rt, 'cudaEventDestroy', [ptr])
    handle = ptr()
    bind(bl, 'cublasCreate_v2', [C.POINTER(ptr)])(C.byref(handle))
    destroy = bind(bl, 'cublasDestroy_v2', [ptr])
    math_mode = bind(bl, 'cublasSetMathMode', [ptr, integer])
    sgemm = bind(bl, 'cublasSgemm_v2', [ptr] + [integer]*5 + [ptr,ptr,integer,ptr,integer,ptr,ptr,integer])
    gemm_ex = bind(bl, 'cublasGemmEx', [ptr] + [integer]*5 + [ptr,ptr,integer,integer,ptr,integer,integer,ptr,ptr,integer,integer,integer,integer])
    runtime_version, blas_version = integer(), integer()
    bind(rt, 'cudaRuntimeGetVersion', [C.POINTER(integer)])(C.byref(runtime_version))
    bind(bl, 'cublasGetVersion_v2', [ptr,C.POINTER(integer)])(handle,C.byref(blas_version))
    measurements = []
    try:
        for name, dtype, compute, math in MODES:
            host = np.ones((n,n), dtype=np.float32) if dtype == 0 else np.full((n,n), 0x3c00 if dtype == 2 else 0x3f80, dtype=np.uint16)
            output = np.empty((n,n), dtype=np.float32)
            a,b,c,start,stop = (ptr() for _ in range(5))
            try:
                for p, count in ((a,host.nbytes),(b,host.nbytes),(c,output.nbytes)):
                    malloc(C.byref(p),count)
                transfer(a,host.ctypes.data,host.nbytes,1)
                transfer(b,host.ctypes.data,host.nbytes,1)
                math_mode(handle,math)
                alpha,beta = C.c_float(1),C.c_float(0)
                def gemm():
                    if compute is None:
                        sgemm(handle,0,0,n,n,n,C.byref(alpha),a,n,b,n,C.byref(beta),c,n)
                    else:
                        gemm_ex(handle,0,0,n,n,n,C.byref(alpha),a,dtype,n,b,dtype,n,C.byref(beta),c,0,n,compute,99)
                # First operation also catches ABI, allocation and algorithm errors.
                gemm();sync()
                transfer(output.ctypes.data,c,output.nbytes,2)
                if not np.all(output == n):
                    raise RuntimeError(f'{name}: reference mismatch before timing')
                began=time.perf_counter()
                while time.perf_counter()-began < warmup:
                    gemm();sync()
                event_create(C.byref(start));event_create(C.byref(stop))
                times=[]
                for _ in range(samples):
                    event_record(start,None);gemm();event_record(stop,None);event_sync(stop)
                    elapsed=C.c_float();event_ms(C.byref(elapsed),start,stop)
                    if elapsed.value <= 0:
                        raise RuntimeError('Invalid CUDA event duration')
                    times.append(elapsed.value)
                transfer(output.ctypes.data,c,output.nbytes,2)
                if not np.all(output == n):
                    raise RuntimeError(f'{name}: reference mismatch after timing')
                median=statistics.median(times)
                measurements.append({'name':name,'n':n,'samples_ms':times,'median_ms':median,
                                     'tflops':2*n**3/(median*1e9),'full_matrix_reference_checked':True})
                print(f'{name}: {measurements[-1]["tflops"]:.3f} TFLOPS',flush=True)
            finally:
                for e in (start,stop):
                    if e.value:event_destroy(e)
                for p in (a,b,c):
                    if p.value:free(p)
    finally:
        destroy(handle)
        dll_dir.close()
    return {'cuda_runtime':runtime_version.value,'cublas':blas_version.value,'modes':measurements}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--trial',type=int)
    ap.add_argument('--output',type=Path)
    ap.add_argument('--smoke',action='store_true')
    args=ap.parse_args()
    if os.environ.get('NVIDIA_TF32_OVERRIDE'):
        raise RuntimeError('NVIDIA_TF32_OVERRIDE is set; cannot compare precision modes')
    if args.trial:
        result=trial(64 if args.smoke else 4096,3 if args.smoke else 30,0.05 if args.smoke else 2.0)
        args.output.write_text(json.dumps(result,indent=2))
        return
    before=telemetry()
    if float(before['utilization.gpu'])>15 or float(before['memory.used'])>2048 or float(before['temperature.gpu'])>65:
        raise RuntimeError('GPU busy or hot; no application was stopped')
    folder=HERE/'benchmark-results'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True,exist_ok=False)
    context={'protocol':'local-ctypes-cublas-v1','gpu_before':before,'smoke':args.smoke,
             'unlock_performed':False,'device_settings_changed':False,
             'warmup_seconds':0.05 if args.smoke else 2.0,
             'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'libraries':{name:hashlib.sha256((LIBDIR/name).read_bytes()).hexdigest()
                          for name in ('cudart64_12.dll','cublas64_12.dll','cublasLt64_12.dll')}}
    (folder/'context.json').write_text(json.dumps(context,indent=2))
    trials=[]
    for number in range(1,2 if args.smoke else 4):
        out=folder/f'trial-{number}.json'
        command=[sys.executable,'-I',str(Path(__file__).resolve()),'--trial',str(number),'--output',str(out)]
        if args.smoke:command.append('--smoke')
        subprocess.run(command,check=True,timeout=180)
        trials.append(json.loads(out.read_text()))
        state=telemetry()
        (folder/f'telemetry-after-{number}.json').write_text(json.dumps(state,indent=2))
        if float(state['temperature.gpu'])>85:
            raise RuntimeError('Temperature above 85 C; stopped further trials')
    summary=[]
    for index,(name,*_) in enumerate(MODES):
        values=[t['modes'][index]['tflops'] for t in trials]
        summary.append({'name':name,'median_tflops':statistics.median(values),
                        'min_tflops':min(values),'max_tflops':max(values)})
    (folder/'summary.json').write_text(json.dumps(summary,indent=2))
    (folder/'complete.json').write_text(json.dumps({'trials':len(trials),'all_outputs_checked':True}))
    print(json.dumps({'results':str(folder),'summary':summary},indent=2))

if __name__=='__main__':
    main()
