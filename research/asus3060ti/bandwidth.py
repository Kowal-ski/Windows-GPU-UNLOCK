"""Read-only bandwidth experiment; no clock/driver changes. GPL-2.0-only.
D2D copy counts read+write bytes. Host paths include synchronization/wall time.
Requires existing CUDA 12 runtime DLL and numpy; does not download anything.
"""
import argparse, ctypes as C, hashlib, json, os, statistics, time
from pathlib import Path
import numpy as np

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cuda-dir',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    handle=os.add_dll_directory(str(args.cuda_dir));rt=C.CDLL(str(args.cuda_dir/'cudart64_12.dll'))
    P=C.c_void_p;I=C.c_int;S=C.c_size_t
    def bind(name,types):
        f=getattr(rt,name);f.argtypes=types;f.restype=I
        def call(*a):
            result=f(*a)
            if result:raise RuntimeError(f'{name}: {result}')
        return call
    dev=I();bind('cudaDeviceGetByPCIBusId',[C.POINTER(I),C.c_char_p])(C.byref(dev),b'0000:01:00.0');bind('cudaSetDevice',[I])(dev)
    alloc=bind('cudaMalloc',[C.POINTER(P),S]);free=bind('cudaFree',[P]);hostalloc=bind('cudaMallocHost',[C.POINTER(P),S]);hostfree=bind('cudaFreeHost',[P]);copy=bind('cudaMemcpy',[P,P,S,I]);sync=bind('cudaDeviceSynchronize',[])
    rows=[];rng=np.random.default_rng(3060)
    for mib in (16,64,256):
        n=mib*1024*1024;a=P();b=P();pinned=P()
        source=rng.integers(0,256,n,dtype=np.uint8);out=np.empty_like(source);expected=hashlib.sha256(source).hexdigest()
        try:
            alloc(C.byref(a),n);alloc(C.byref(b),n);hostalloc(C.byref(pinned),n);C.memmove(pinned,int(source.ctypes.data),n)
            for mode,src,dst,kind,factor in [('H2D_pageable',source.ctypes.data,a,1,1),('H2D_pinned',pinned,a,1,1),('D2D',a,b,3,2),('D2H_pageable',a,out.ctypes.data,2,1),('D2H_pinned',a,pinned,2,1)]:
                for _ in range(3):copy(dst,src,n,kind);sync()
                times=[]
                for _ in range(12):
                    began=time.perf_counter();copy(dst,src,n,kind);sync();times.append(time.perf_counter()-began)
                check=b if mode=='D2D' else a
                if mode=='D2H_pinned':C.memmove(int(out.ctypes.data),pinned,n)
                elif mode!='D2H_pageable':copy(out.ctypes.data,check,n,2)
                if hashlib.sha256(out).hexdigest()!=expected:raise RuntimeError('Full buffer mismatch: '+mode)
                row={'MiB':mib,'mode':mode,'median_GB_s':n*factor/statistics.median(times)/1e9,'samples_seconds':times,'full_buffer_checked':True,'bytes_counted_per_copy':n*factor};rows.append(row)
                print(f'{mib} MiB {mode}: {row["median_GB_s"]:.2f} GB/s',flush=True)
        finally:
            for p in (a,b):
                if p.value:free(p)
            if pinned.value:hostfree(pinned)
    result={'protocol':'synchronous-copy-wallclock-v1','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cuda_runtime_sha256':hashlib.sha256((args.cuda_dir/'cudart64_12.dll').read_bytes()).hexdigest(),'settings_changed':False,'limits':'Single process, existing desktop activity uncontrolled. D2D copy is not a general kernel/LLM bandwidth result; no before-unlock comparison. Decimal GB/s; D2D counts read plus write.','rows':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2));handle.close()
if __name__=='__main__':main()
