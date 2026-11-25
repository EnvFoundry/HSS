import {test} from 'node:test';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
import {HSSClient,SelectionSet} from '../lib/client.js';
import {pythonTransport} from '../node.mjs';
test('Selection remains shared across field and filter views',()=>{
  const set=new SelectionSet();set.addAll(['corpus-assembly','text-collation']);set.addAll(['corpus-assembly','prediction']);
  assert.deepEqual(set.list(),['corpus-assembly','text-collation','prediction']);set.set('prediction',false);assert.equal(set.list().length,2);
});
test('Host space and selected software settings reach the request',async()=>{
  let received;const client=new HSSClient(async q=>{received=q;return {modules:[]};},'/research');
  await client.prepare(['concept-analysis'],{software:false});
  assert.equal(received.space,'/research');assert.equal(received.software,false);assert.deepEqual(received.selections,['concept-analysis']);
});
test('Node transport calls actual Python catalogue',async()=>{
  const root=fileURLToPath(new URL('../../../',import.meta.url));
  const client=new HSSClient(pythonTransport({python:process.env.PYTHON||'python',pythonPath:resolve(root,'src')}));
  const catalogue=await client.browse();assert.ok(catalogue.fields.length>10);
  const plan=await client.plan([]);assert.equal(plan.modules.length,0);
});
