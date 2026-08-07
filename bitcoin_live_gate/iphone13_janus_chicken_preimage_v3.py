#!/usr/bin/env python3
"""JANUS iPhone/a-Shell live Stratum runner v3.

Terminal rule:
- accepted nerdminer-sequential share => CONTROL only, continue;
- accepted janus-permuted share => write exact 80-byte preimage witness and stop.

The witness is the exact Bitcoin block-header input to SHA256d, rendered as JSON/TXT.
It is not a claim that arbitrary human plaintext can be recovered from SHA-256.
"""
import argparse, json, socket, time
from pathlib import Path
from nerdminer_v2_janus_bridge import (
    StratumJob, base58check_valid, compact_to_target, difficulty_to_target,
    dsha, fixed_extranonce2, hash_difficulty, hash_value, header_with_nonce,
    janus_nonces, merkle_root, nerdminer_header_prefix, sequential_nonces,
    scan, selftest, NERDMINER_START_NONCE,
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
        finally: self.s.settimeout(old)
    def poll(self, timeout=0.0):
        try:return self.read(timeout)
        except (socket.timeout,BlockingIOError):return None
    def close(self):
        try:self.s.close()
        except:pass

def log(event, **k):
    row={'ts':time.time(),'event':event,**k}; print(json.dumps(row,separators=(',',':')),flush=True)

def printable(data):
    return ''.join(chr(b) if 32<=b<=126 else '.' for b in data)

def fragments(data, min_len=4):
    out=[]; cur=bytearray()
    for b in data:
        if 32<=b<=126 or b>=0xC2: cur.append(b)
        else:
            if len(cur)>=min_len:
                s=cur.decode('utf-8','ignore').strip()
                if len(s)>=min_len: out.append(s)
            cur.clear()
    if len(cur)>=min_len:
        s=cur.decode('utf-8','ignore').strip()
        if len(s)>=min_len: out.append(s)
    return out

def witness(job, ex1, ex2, nonce, accepted_hash, achieved, share_diff, pool, worker):
    coinbase_hex=job.coinb1+ex1+ex2+job.coinb2; cb=bytes.fromhex(coinbase_hex)
    mr=merkle_root(job,ex1,ex2); prefix=nerdminer_header_prefix(job,ex1,ex2)
    header=header_with_nonce(prefix,nonce); digest=dsha(header); replay=digest[::-1].hex()
    return {
      'witness_type':'JANUS_ACCEPTED_BITCOIN_SHARE_EXACT_PREIMAGE',
      'scientific_boundary':'Exact 80-byte Bitcoin block-header preimage of the accepted SHA256d share; not arbitrary plaintext recovery.',
      'strategy':'janus-permuted','pool':pool,'payout_worker':worker,'job_id':job.job_id,
      'accepted_hash_display_hex':accepted_hash,'achieved_difficulty':achieved,
      'share_difficulty_at_scan':share_diff,'header_length_bytes':len(header),'header_hex':header.hex(),
      'header_printable_projection':printable(header),
      'header_fields':{
        'version_stratum_hex':job.version,'version_header_le_hex':header[0:4].hex(),
        'previous_block_hash_stratum_hex':job.prevhash,'previous_block_hash_header_bytes_hex':header[4:36].hex(),
        'merkle_root_digest_hex':mr.hex(),'merkle_root_header_bytes_hex':header[36:68].hex(),
        'ntime_stratum_hex':job.ntime,'ntime_header_le_hex':header[68:72].hex(),
        'nbits_stratum_hex':job.nbits,'nbits_header_le_hex':header[72:76].hex(),
        'nonce_uint32':nonce,'nonce_hex':f'{nonce:08x}','nonce_header_le_hex':header[76:80].hex()},
      'extranonce1':ex1,'extranonce2':ex2,'coinbase_hex':coinbase_hex,'coinbase_length_bytes':len(cb),
      'coinbase_printable_projection':printable(cb),'coinbase_text_fragments':fragments(cb),
      'merkle_branch':job.merkle_branch,
      'replay':{'sha256d_header_display_hex':replay,'matches_accepted_hash':replay==accepted_hash,
                'meets_scanned_share_target':hash_value(digest)<=difficulty_to_target(share_diff),
                'meets_network_target':hash_value(digest)<=compact_to_target(job.nbits)},
      'canonical_text':f'JANUS accepted share preimage\njob_id={job.job_id}\nversion={job.version}\nprevhash={job.prevhash}\nmerkle_root={mr.hex()}\nntime={job.ntime}\nnbits={job.nbits}\nnonce={nonce:08x}\nextranonce1={ex1}\nextranonce2={ex2}\nheader_hex={header.hex()}\nsha256d={replay}\n'}

def write_witness(base, w):
    stem=Path(base); jp=Path(str(stem)+'_JANUS_CHICKEN_WITNESS.json'); tp=Path(str(stem)+'_JANUS_CHICKEN_WITNESS.txt')
    jp.write_text(json.dumps(w,ensure_ascii=False,indent=2),encoding='utf-8')
    txt=w['canonical_text']+'\ncoinbase_text_fragments:\n'+''.join(f'- {x}\n' for x in w['coinbase_text_fragments'])+'\nverification:\n'+json.dumps(w['replay'],ensure_ascii=False,indent=2)+'\n'
    tp.write_text(txt,encoding='utf-8'); return str(jp),str(tp)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--pool',default=DEFAULT_POOL); ap.add_argument('--port',type=int,default=DEFAULT_PORT)
    ap.add_argument('--wallet',default=DEFAULT_WALLET); ap.add_argument('--worker',default='JANUS-IP13'); ap.add_argument('--hashes',type=int,default=500000)
    ap.add_argument('--pause',type=float,default=0.2); ap.add_argument('--selftest',action='store_true'); a=ap.parse_args(); worker=f'{a.wallet}.{a.worker}'
    if not base58check_valid(a.wallet): raise SystemExit('bad wallet')
    log('ouroboros',**selftest())
    if a.selftest:return 0
    runbase=f'JANUS_IPHONE13_{int(time.time())}'; w=Wire(a.pool,a.port); pending={}; job=None; epoch=0; diff=.00015; ex1=''; ex2size=4; ex2counter=1
    janus_done=False; seq_accept=0; jan_accept=0
    try:
      sid=w.send('mining.subscribe',['NerdMinerV2/JANUS-iPhone13-PREIMAGE-v3'])
      while True:
        m=w.read(); log('rx',payload=m)
        if m.get('id')==sid: ex1=str(m['result'][1]); ex2size=int(m['result'][2]); break
      w.send('mining.authorize',[worker,'x']); w.send('mining.suggest_difficulty',[.00015])
      def handle(m):
        nonlocal job,epoch,diff,janus_done,seq_accept,jan_accept
        log('rx',payload=m); method=m.get('method')
        if method=='mining.set_difficulty': diff=float(m['params'][0]); log('pool_difficulty',difficulty=diff); return
        if method=='mining.notify': job=StratumJob.from_notify(m['params']); epoch+=1; log('job_received',job_id=job.job_id,epoch=epoch,clean=job.clean_jobs); return
        rid=m.get('id')
        if rid in pending:
          meta=pending.pop(rid); ok=m.get('result') is True and not m.get('error')
          logmeta={k:v for k,v in meta.items() if k!='job'}; log('share_confirmation',accepted=ok,submit_id=rid,**logmeta)
          if ok and meta['strategy']=='janus-permuted':
            jan_accept+=1; ww=witness(meta['job'],ex1,meta['ex2'],meta['nonce_i'],meta['hash'],meta['difficulty'],meta['share_diff'],f'{a.pool}:{a.port}',worker)
            jp,tp=write_witness(runbase,ww); janus_done=True
            log('JANUS_CHICKEN_FOUND',submit_id=rid,hash=meta['hash'],nonce=meta['nonce'],replay_matches=ww['replay']['matches_accepted_hash'],witness_json=jp,witness_txt=tp)
          elif ok:
            seq_accept+=1; log('CONTROL_CHICKEN_ACCEPTED_CONTINUE',submit_id=rid,sequential_accepted_shares=seq_accept,**logmeta)
      while job is None: handle(w.read())
      round_no=0
      while not janus_done:
        while True:
          m=w.poll(0.0)
          if m is None:break
          handle(m)
        round_no+=1; snap=job; snap_epoch=epoch; snap_diff=diff
        ex2=(ex2counter%(1<<(8*ex2size))).to_bytes(ex2size,'big').hex(); ex2counter+=1
        prefix=nerdminer_header_prefix(snap,ex1,ex2); nt=compact_to_target(snap.nbits)
        seq,sh=scan(prefix,sequential_nonces(a.hashes,NERDMINER_START_NONCE),snap_diff,nt,'nerdminer-sequential')
        jan,jh=scan(prefix,janus_nonces(a.hashes,prefix,NERDMINER_START_NONCE),snap_diff,nt,'janus-permuted')
        log('paired_result',round=round_no,job_id=snap.job_id,difficulty=snap_diff,seq_best=seq.best_difficulty,janus_best=jan.best_difficulty,seq_hits=seq.share_hits,janus_hits=jan.share_hits,winner=('janus' if jan.best_difficulty>seq.best_difficulty else 'sequential'))
        while True:
          m=w.poll(0.0)
          if m is None:break
          handle(m)
        if epoch!=snap_epoch: log('stale_round_no_submit',old_job=snap.job_id); continue
        for strategy,hits in [('nerdminer-sequential',sh),('janus-permuted',jh)]:
          for nonce,h in hits:
            submit_id=w.send('mining.submit',[worker,snap.job_id,ex2,snap.ntime,f'{nonce:08x}'])
            pending[submit_id]={'strategy':strategy,'job_id':snap.job_id,'job':snap,'ex2':ex2,'nonce':f'{nonce:08x}','nonce_i':nonce,'hash':h,'difficulty':hash_difficulty(bytes.fromhex(h)[::-1]),'share_diff':snap_diff}
            log('share_submitted',submit_id=submit_id,**{k:v for k,v in pending[submit_id].items() if k!='job'})
        until=time.time()+2.0
        while time.time()<until and pending and not janus_done:
          m=w.poll(.1)
          if m is not None:handle(m)
        if a.pause:time.sleep(a.pause)
      log('janus_stop',reason='janus_accepted_share_found',sequential_accepted_shares=seq_accept,janus_accepted_shares=jan_accept)
    except KeyboardInterrupt: log('stopped',reason='keyboard_interrupt')
    finally:w.close()
    return 0
if __name__=='__main__':raise SystemExit(main())
