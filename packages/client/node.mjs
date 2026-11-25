import {spawn} from 'node:child_process';
/** Use this in the host backend, never directly in a browser renderer. */
export function pythonTransport({python='python', pythonPath, environment={}}={}) {
  return (request, progress) => new Promise((resolve,reject)=>{
    const env={...process.env,...environment};
    if(pythonPath)env.PYTHONPATH=pythonPath+(env.PYTHONPATH?(process.platform==='win32'?';':':')+env.PYTHONPATH:'');
    const child=spawn(python,['-m','hss','request','-'],{env,stdio:['pipe','pipe','pipe']});
    let output='',errors='',partial='';
    child.stdout.setEncoding('utf8');child.stderr.setEncoding('utf8');
    child.stdout.on('data',chunk=>{output+=chunk;});
    child.stderr.on('data',chunk=>{errors+=chunk;partial+=chunk;const lines=partial.split('\n');partial=lines.pop();for(const line of lines){try{const event=JSON.parse(line);if(event.component&&event.step)progress?.(event);}catch{}}});
    child.on('error',reject);
    child.on('close',code=>{if(code!==0&&code!==2){reject(new Error(errors.trim()||`HSS exited with ${code}`));return;}try{resolve(JSON.parse(output));}catch{reject(new Error('HSS returned no JSON result: '+errors));}});
    child.stdin.on('error',()=>{});child.stdin.end(JSON.stringify(request));
  });
}
