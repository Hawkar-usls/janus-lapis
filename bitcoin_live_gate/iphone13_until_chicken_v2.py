#!/usr/bin/env python3
"""JANUS iPhone/a-Shell continuous Stratum runner.

Keeps mining the current valid job across fresh extranonce2 spaces and stops
only after the pool confirms a submitted share with result:true.
Uses the tested primitives from nerdminer_v2_janus_bridge.py.
"""
import argparse, json, socket, time
from nerdminer_v2_janus_bridge import (
    StratumJob, base58check_valid, compact_to_target, fixed_extranonce2,
    hash_difficulty, janus_nonces, nerdminer_header_prefix,
    sequential_nonces, scan, selftest, NERDMINER_START_NONCE,
)

DEFAULT_POOL='solobtc.nmminer.com'; DEFAULT_PORT=3333
DEFAULT_WALLET='1F1Y6CdkApZboDF6g1DYrQ8Dke2E5gWiP1'

class Wire:
    def __init__(self, host, port, timeout=30):
        self.s=socket.create_connection((host,port),timeout=timeout)
        self.s.settimeout(timeout); self.buf=b''; self.i=0; self.timeout=timeout
    def send(self, method, params):
        self.i+=1; obj={'id':self.i,'method':method,'params':params}
        self.s.sendall((json.dumps(obj,separators=(',',':'))+'\n').encode()); return self.i
    def read(self, timeout=None):
        old=self.s.gettimeout(); self.s.settimeout(self.timeout if timeout is None else timeout)
        try:
            while b'\n' not in self.buf:
                b=self.s.recv(65536)
                if not b: raise EOFError('pool closed connection')
                self.buf+=b
            line,self.buf=self.buf.split(b'\n',1)
            return json.loads(line)
        finally:
            self.s.settimeout(old)
    def poll(self, timeout=0.0):
        try: return self.read(timeout)
        except (socket.timeout,BlockingIOError): return None
    def close(self):
        try:self.s.close()
        except:pass

def log(event, **k):
    row={'ts':time.time(),'event':event,**k}; print(json.dumps(row,separators=(',',':')),flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--pool',default=DEFAULT_POOL); ap.add_argument('--port',type=int,default=DEFAULT_PORT)
    ap.add_argument('--wallet',default=DEFAULT_WALLET); ap.add_argument('--worker',default='JANUS-IP13')
    ap.add_argument('--hashes',type=int,default=500000); ap.add_argument('--pause',type=float,default=0.2)
    a=ap.parse_args(); worker=f'{a.wallet}.{a.worker}'
    if not base58check_valid(a.wallet): raise SystemExit('bad wallet')
    log('ouroboros', **selftest())
    w=Wire(a.pool,a.port); pending={}; job=None; epoch=0; diff=0.00015; ex1=''; ex2size=4; ex2counter=1; chicken=False
    try:
        sid=w.send('mining.subscribe',['NerdMinerV2/JANUS-iPhone13-aShell-v2'])
        while True:
            m=w.read(); log('rx',payload=m)
            if m.get('id')==sid:
                ex1=str(m['result'][1]); ex2size=int(m['result'][2]); break
        w.send('mining.authorize',[worker,'x']); w.send('mining.suggest_difficulty',[0.00015])
        def handle(m):
            nonlocal job,epoch,diff,chicken
            log('rx',payload=m); method=m.get('method')
            if method=='mining.set_difficulty': diff=float(m['params'][0]); log('pool_difficulty',difficulty=diff); return
            if method=='mining.notify': job=StratumJob.from_notify(m['params']); epoch+=1; log('job_received',job_id=job.job_id,epoch=epoch,clean=job.clean_jobs); return
            rid=m.get('id')
            if rid in pending:
                meta=pending.pop(rid); ok=m.get('result') is True and not m.get('error')
                log('share_confirmation',accepted=ok,submit_id=rid,**meta)
                if ok: chicken=True; log('CHICKEN_FOUND',**meta)
        while job is None:
            handle(w.read())
        round_no=0
        while not chicken:
            while True:
                m=w.poll(0.0)
                if m is None: break
                handle(m)
            if chicken: break
            round_no+=1; snap=job; snap_epoch=epoch; snap_diff=diff
            ex2=(ex2counter % (1<<(8*ex2size))).to_bytes(ex2size,'big').hex(); ex2counter+=1
            prefix=nerdminer_header_prefix(snap,ex1,ex2); nt=compact_to_target(snap.nbits)
            seq,sh=scan(prefix,sequential_nonces(a.hashes,NERDMINER_START_NONCE),snap_diff,nt,'nerdminer-sequential')
            jan,jh=scan(prefix,janus_nonces(a.hashes,prefix,NERDMINER_START_NONCE),snap_diff,nt,'janus-permuted')
            log('paired_result',round=round_no,job_id=snap.job_id,difficulty=snap_diff,seq_best=seq.best_difficulty,janus_best=jan.best_difficulty,seq_hits=seq.share_hits,janus_hits=jan.share_hits,winner=('janus' if jan.best_difficulty>seq.best_difficulty else 'sequential'))
            while True:
                m=w.poll(0.0)
                if m is None: break
                handle(m)
            if epoch!=snap_epoch:
                log('stale_round_no_submit',old_job=snap.job_id); continue
            for strategy,hits in [('nerdminer-sequential',sh),('janus-permuted',jh)]:
                for nonce,h in hits:
                    submit_id=w.send('mining.submit',[worker,snap.job_id,ex2,snap.ntime,f'{nonce:08x}'])
                    pending[submit_id]={'strategy':strategy,'job_id':snap.job_id,'nonce':f'{nonce:08x}','hash':h,'difficulty':hash_difficulty(bytes.fromhex(h)[::-1])}
                    log('share_submitted',submit_id=submit_id,**pending[submit_id])
            until=time.time()+2.0
            while time.time()<until and pending and not chicken:
                m=w.poll(0.1)
                if m is not None: handle(m)
            if a.pause: time.sleep(a.pause)
    except KeyboardInterrupt:
        log('stopped','keyboard_interrupt')
    finally:
        w.close()
    return 0
if __name__=='__main__': raise SystemExit(main())
