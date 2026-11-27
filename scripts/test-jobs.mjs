import assert from 'node:assert/strict';
import {test} from 'node:test';
import {jobResult} from '../src/agenda_radar/static/jobs.js';

test('job callers share polling, back off and release completed jobs',async t=>{
  t.mock.timers.enable({apis:['setTimeout','Date']});
  let calls=0;
  const api=async()=>({status:++calls===2?'done':'pending',result:{answer:'Ready'}});
  const first=jobResult(1,api,()=>{});
  assert.equal(first,jobResult(1,api,()=>{}));
  t.mock.timers.tick(1500);
  await Promise.resolve();await Promise.resolve();
  assert.equal(calls,1);
  t.mock.timers.tick(2249);
  await Promise.resolve();
  assert.equal(calls,1);
  t.mock.timers.tick(1);
  assert.deepEqual(await first,{answer:'Ready'});
  const again=jobResult(1,async()=>({status:'done',result:'Fresh'}),()=>{});
  assert.notEqual(first,again);
  t.mock.timers.tick(1500);
  assert.equal(await again,'Fresh');
});

test('failed jobs can be retried and pending jobs expire',async t=>{
  t.mock.timers.enable({apis:['setTimeout','Date']});
  const failed=jobResult(2,async()=>({status:'failed',error_code:'test'}),()=>{});
  const failure=assert.rejects(failed,/test/);
  t.mock.timers.tick(1500);await failure;
  const retry=jobResult(2,async()=>({status:'done',result:'OK'}),()=>{});
  t.mock.timers.tick(1500);assert.equal(await retry,'OK');
  const pending=jobResult(3,async()=>({status:'pending'}),()=>{});
  const timeout=assert.rejects(pending,/sigue pendiente/);
  t.mock.timers.tick(180000);await timeout;
});
