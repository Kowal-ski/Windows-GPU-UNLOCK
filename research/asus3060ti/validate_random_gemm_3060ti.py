"""Supplemental integer-valued random GEMMs; 60-second local stability screen.

No device settings or firmware changes. Not a general numerical certification
or proof of stability in every application. Small integer inputs are exactly
representable in all tested formats, so the FP32 output must match exactly.
"""
import argparse
import ctypes as C
import datetime
import hashlib
import json
import os
from pathlib import Path
import time
import numpy as np
import benchmark_3060ti as bench

HERE = Path(__file__).resolve().parent


def require_reference(output, reference):
    if not np.array_equal(output, reference):
        raise RuntimeError(f'Nonuniform matrix mismatch; max error {np.max(np.abs(output-reference))}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=int, default=60, choices=range(4, 601))
    parser.add_argument('--stress-size', type=int, default=1024, choices=(1024, 2048, 4096))
    args = parser.parse_args()
    if os.environ.get('NVIDIA_TF32_OVERRIDE'):
        raise RuntimeError('TF32 override prevents controlled validation')
    before = bench.telemetry()
    if float(before['utilization.gpu']) > 15 or float(before['temperature.gpu']) > 70:
        raise RuntimeError('GPU busy or hot')
    # Negative control proves that output corruption is detected.
    try:
        require_reference(np.array([1, 2], dtype=np.float32), np.array([1, 3], dtype=np.float32))
    except RuntimeError:
        pass
    else:
        raise AssertionError('Negative reference control failed')
    dll_dir = os.add_dll_directory(str(bench.LIBDIR))
    rt = C.CDLL(str(bench.LIBDIR/'cudart64_12.dll'))
    bl = C.CDLL(str(bench.LIBDIR/'cublas64_12.dll'))
    ptr, integer = C.c_void_p, C.c_int
    device = integer()
    bench.bind(rt, 'cudaDeviceGetByPCIBusId', [C.POINTER(integer), C.c_char_p])(C.byref(device), b'0000:01:00.0')
    bench.bind(rt, 'cudaSetDevice', [integer])(device)
    malloc = bench.bind(rt, 'cudaMalloc', [C.POINTER(ptr), C.c_size_t])
    free = bench.bind(rt, 'cudaFree', [ptr])
    copy = bench.bind(rt, 'cudaMemcpy', [ptr, ptr, C.c_size_t, integer])
    sync = bench.bind(rt, 'cudaDeviceSynchronize', [])
    handle = ptr()
    bench.bind(bl, 'cublasCreate_v2', [C.POINTER(ptr)])(C.byref(handle))
    destroy = bench.bind(bl, 'cublasDestroy_v2', [ptr])
    math_mode = bench.bind(bl, 'cublasSetMathMode', [ptr, integer])
    sgemm = bench.bind(bl, 'cublasSgemm_v2', [ptr]+[integer]*5+[ptr,ptr,integer,ptr,integer,ptr,ptr,integer])
    gemm_ex = bench.bind(bl, 'cublasGemmEx', [ptr]+[integer]*5+[ptr,ptr,integer,integer,ptr,integer,integer,ptr,ptr,integer,integer,integer,integer])
    rng = np.random.default_rng(20261029)
    rows, telemetry = [], [before]
    try:
        for n in (61, 257, args.stress_size):
            left = np.asfortranarray(rng.integers(-3, 4, size=(n,n)).astype(np.float32))
            right = np.asfortranarray(rng.integers(-3, 4, size=(n,n)).astype(np.float32))
            reference = (left.astype(np.float64) @ right.astype(np.float64)).astype(np.float32)
            for name, dtype, compute, math in bench.MODES:
                def pack(value):
                    if dtype == 0:
                        return value
                    if dtype == 2:
                        return np.asfortranarray(value.astype(np.float16))
                    return np.asfortranarray((value.view(np.uint32) >> 16).astype(np.uint16))
                ha, hb = pack(left), pack(right)
                output = np.empty((n,n), dtype=np.float32, order='F')
                a, b, c = ptr(), ptr(), ptr()
                try:
                    for device_ptr, host in ((a,ha),(b,hb),(c,output)):
                        malloc(C.byref(device_ptr),host.nbytes)
                    copy(a,ha.ctypes.data,ha.nbytes,1);copy(b,hb.ctypes.data,hb.nbytes,1)
                    math_mode(handle,math)
                    alpha,beta=C.c_float(1),C.c_float(0)
                    def run():
                        if compute is None:
                            sgemm(handle,0,0,n,n,n,C.byref(alpha),a,n,b,n,C.byref(beta),c,n)
                        else:
                            gemm_ex(handle,0,0,n,n,n,C.byref(alpha),a,dtype,n,b,dtype,n,C.byref(beta),c,0,n,compute,99)
                    began=time.perf_counter();iterations=checks=0;next_temp=began+5
                    while True:
                        for _ in range(64 if n==args.stress_size else 1):
                            run();iterations+=1
                        sync();copy(output.ctypes.data,c,output.nbytes,2)
                        require_reference(output,reference);checks+=1
                        now=time.perf_counter()
                        if now>=next_temp:
                            state=bench.telemetry();telemetry.append(state);next_temp=now+5
                            if float(state['temperature.gpu'])>85:
                                raise RuntimeError('Temperature exceeds 85 C; stopped')
                        if n!=args.stress_size or now-began>=args.seconds/len(bench.MODES):
                            break
                    rows.append({'mode':name,'n':n,'gemms':iterations,'full_output_checks':checks,
                                 'seconds':time.perf_counter()-began,'max_absolute_error':0})
                    print(f'PASS {name} n={n} GEMMs={iterations} checks={checks}',flush=True)
                finally:
                    for device_ptr in (a,b,c):
                        if device_ptr.value:free(device_ptr)
    finally:
        destroy(handle);dll_dir.close()
    telemetry.append(bench.telemetry())
    report={'passed':True,'seed':20261029,'input_range':[-3,3],'negative_control_passed':True,
            'requested_stress_seconds':args.seconds,'stress_size':args.stress_size,
            'cases':rows,'telemetry_samples':telemetry,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope':'short local GEMM correctness/stability screen; not every workload'}
    target=HERE/'random-validation-results'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    target.mkdir(parents=True,exist_ok=False)
    (target/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(target)


if __name__=='__main__':
    main()
