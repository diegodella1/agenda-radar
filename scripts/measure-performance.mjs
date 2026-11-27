import {mkdir, writeFile} from "node:fs/promises";
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const base = process.env.SMOKE_BASE_URL || "http://127.0.0.1:8791";
const browser = await chromium.launch({executablePath:"/usr/bin/chromium",args:["--no-sandbox"]});
const results=[];
try {
 for (const width of [390,1440]) {
  const context=await browser.newContext({viewport:{width,height:950}});
  let login;
  const loginDeadline=Date.now()+180000;
  do {
   login=await context.request.post(base+"/demo/api/v1/auth/login",{headers:{"X-Requested-With":"AgendaRadar"},data:{email:"demo",password:"demo"}});
   if(login.status()===202)await new Promise(resolve=>setTimeout(resolve,500));
  } while(login.status()===202 && Date.now()<loginDeadline);
  if(login.status()!==200)throw new Error(await login.text());
  await context.addInitScript(()=>{
   sessionStorage.setItem("radar-demo-tour",JSON.stringify({version:1,status:"skipped",step:0,eventUrl:null}));
   window.measurement={cls:0,longTasks:0};
   new PerformanceObserver(list=>{for(const e of list.getEntries())if(!e.hadRecentInput)window.measurement.cls+=e.value;}).observe({type:"layout-shift",buffered:true});
   new PerformanceObserver(list=>{window.measurement.longTasks+=list.getEntries().length;}).observe({type:"longtask",buffered:true});
  });
  const page=await context.newPage();
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  const cdp=await context.newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions",{offline:false,latency:80,downloadThroughput:200000,uploadThroughput:100000});
  await cdp.send("Emulation.setCPUThrottlingRate",{rate:4});
  for(const path of ["/home","/login","/demo/","/demo/admin/config"]){
   for(let run=0;run<3;run++){
    await cdp.send("Network.clearBrowserCache");
    for(const cache of ["cold","warm"]){
     const response=await page.goto(base+path,{waitUntil:"networkidle"});
     if(response.status()!==200)throw new Error(`${path}: HTTP ${response.status()}`);
     await page.evaluate(()=>document.fonts.ready);
     await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
     results.push({width,path,run,cache,...await page.evaluate(()=>{
      const resources=performance.getEntriesByType("resource"),nav=performance.getEntriesByType("navigation")[0];
      return {...window.measurement,bytes:resources.reduce((sum,r)=>sum+r.transferSize,nav.transferSize),requests:resources.length+1,domContentLoaded:nav.domContentLoadedEventEnd,resources:resources.map(r=>({url:r.name.split(location.origin)[1],bytes:r.transferSize}))};
     })});
    }
   }
  }
  if(errors.length)throw new Error(errors.join('\n'));
  await context.close();
 }
 await mkdir("artifacts/performance",{recursive:true});
 const label=process.env.PERF_LABEL || "current";
 await writeFile(`artifacts/performance/${label}.json`,JSON.stringify(results,null,2));
 console.log(JSON.stringify(results.map(({resources,...result})=>result),null,2));
}finally{await browser.close();}
