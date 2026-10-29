"""Bounded CPU/RAM microbenchmarks. No system settings changed. GPL-2.0-only."""
import argparse,hashlib,json,os,statistics,subprocess,sys,time
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--threads',type=int,choices=(4,8));ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    if args.threads:
        import numpy as np
        n=1536;a=np.ones((n,n),np.float32);b=np.ones_like(a);out=np.empty_like(a)
        np.matmul(a,b,out=out);times=[]
        for _ in range(9):
            start=time.perf_counter();np.matmul(a,b,out=out);times.append(time.perf_counter()-start)
        if not np.all(out==n):raise RuntimeError('Matrix output mismatch')
        result={'requested_threads':args.threads,'median_GFLOPS':2*n**3/statistics.median(times)/1e9,'samples_seconds':times,'full_matrix_checked':True}
        args.output.write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True);return
    import numpy as np
    source=np.random.default_rng(10100).integers(0,256,256*1024*1024,dtype=np.uint8);dest=np.empty_like(source);samples=[]
    for index in range(15):
        start=time.perf_counter();np.copyto(dest,source);elapsed=time.perf_counter()-start
        if index>=3:samples.append(elapsed)
    if hashlib.sha256(source).digest()!=hashlib.sha256(dest).digest():raise RuntimeError('RAM copy mismatch')
    args.output.parent.mkdir(parents=True,exist_ok=True);rows=[]
    for threads in (4,8):
        env=dict(os.environ);env.update(OPENBLAS_NUM_THREADS=str(threads),OMP_NUM_THREADS=str(threads),MKL_NUM_THREADS=str(threads))
        target=args.output.with_name('cpu-'+str(threads)+'.json')
        subprocess.run([sys.executable,str(Path(__file__).resolve()),'--threads',str(threads),'--output',str(target)],env=env,check=True,timeout=90)
        rows.append(json.loads(target.read_text()))
    result={'protocol':'cpu-ram-observational-v1','RAM_copy_256MiB_read_plus_write_GB_s':2*source.nbytes/statistics.median(samples)/1e9,'RAM_copy_samples_seconds':samples,'CPU_GEMM':rows,'settings_changed':False,'limits':'One run with uncontrolled desktop load; requested BLAS threads are not independently verified. FP32 GEMM and RAM copy are not LLM tokens/s or a hardware memory-controller measurement. No CPU frequency/thermal telemetry.'}
    args.output.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
