'use strict';
const ROOT='/sdcard/Android/data/com.yumekuro.local/files/';
const keep=[];let installed=false,providerReady=false,providerFailed=false;
function log(event,data){
 try{const f=new File(ROOT+'offline/runtime.log','a');f.write(JSON.stringify({time:Date.now(),event,data})+'\n');f.flush();f.close()}catch(_){}
 console.log('[YumeLocal] '+event+' '+JSON.stringify(data??''));
}
function managed(p){try{return p.isNull()?null:p.add(20).readUtf16String(Math.min(p.add(16).readS32(),8000))}catch(_){return null}}
function install(m){
 if(installed)return;installed=true;
 const base=m.base;
 function ensureProvider(){
  if(providerReady||providerFailed)return;
  try{installLocalProvider(m,log,keep);providerReady=true}
  catch(e){providerFailed=true;log('local_provider_initialization_failed',String(e.stack||e))}
 }
 for(const rva of [0x308ae98,0x308a368,0x308a47c,0x308aff8]){
  keep.push(Interceptor.attach(base.add(rva),{onEnter(){ensureProvider()}}));
 }
 let exceptions=0;
 const exceptionText=new NativeFunction(base.add(0x3be45cc),'pointer',['pointer','pointer']);
 keep.push(Interceptor.attach(base.add(0x4dfa4f8),{onEnter(args){
  if(exceptions++<30)try{log('async_exception',{message:managed(args[0].add(0x18).readPointer()),detail:managed(exceptionText(args[0],ptr(0)))})}catch(e){log('exception_diagnostic_error',String(e))}
 }}));
 // Observe real Unity voice playback, without changing audio or scheduling.
 const audioClip=new NativeFunction(base.add(0x3198a00),'pointer',['pointer','pointer']);
 const objectName=new NativeFunction(base.add(0x670b04c),'pointer',['pointer','pointer']);
 const audioPlaying=new NativeFunction(base.add(0x3198cc4),'bool',['pointer','pointer']);
 let voices=0;
 for(const rva of [0x661b6bc,0x661b56c]){
  keep.push(Interceptor.attach(base.add(rva),{
   onEnter(args){
    this.voice=null;
    if(voices>=160)return;
    try{const array=args[0].add(0x20).readPointer(),index=args[0].add(0x68).readS32();
     if(array.isNull() || index<0 || index>=array.add(0x18).readU64().toNumber())return;
     const source=array.add(0x20+index*8).readPointer();
     if(source.isNull())return;
     const clip=audioClip(source,ptr(0));if(clip.isNull())return;
     const name=managed(objectName(clip,ptr(0)));
     if(name && name.startsWith('vo_')){this.voice=name;this.source=source;voices++}
    }catch(e){log('audio_diagnostic_error',String(e))}
   },
   onLeave(){if(this.voice)try{log('audio_voice_started',{clip:this.voice,playing:audioPlaying(this.source,ptr(0))})}catch(e){log('audio_diagnostic_error',String(e))}}
  }));
 }
 let logs=0;
 keep.push(Interceptor.attach(base.add(0x5d09f34),{onEnter(args){if(logs++<150)log('unity_log',{type:args[2].toInt32(),message:managed(args[0]),stack:managed(args[1])})}}));
 const stages=[['Bootstrap.Boot',0x4268f20],['Bootstrap.InitPersist',0x42697e0],['Bootstrap.InitSound',0x4269a28],['Caution.MoveNext',0x2c5e540],['Caution.GoNext',0x2c5e448],['PAD.LoadAll',0x308ae98],['Loading.Hide',0x34366a4],['Environment.SetupApi',0x426c5d0]];
 for(const [name,rva] of stages){let n=0;keep.push(Interceptor.attach(base.add(rva),{onEnter(){if(n++<6)log('stage',name)}}))}
 for(const [name,rva] of [['PAD.Streaming',0x308a368],['PAD.StreamingNamed',0x308a47c],['PAD.Path',0x308cfc0],['PAD.AssetPack',0x308aff8]]){
  let n=0;keep.push(Interceptor.attach(base.add(rva),{onEnter(args){if(n++<180)log(name,managed(args[0]))}}));
 }
 let loads=0;
 keep.push(Interceptor.attach(base.add(0x46a7b40),{onEnter(args){if(loads++<250)log('octo_asset',managed(args[1]))}}));
 for(const [name,rva] of [['PAD.IsAssetCached',0x308d0b4],['Standalone.IsCached',0x5168244]]){
  const seen=new Set();keep.push(Interceptor.attach(base.add(rva),{
   onEnter(args){const path=managed(args[0]);this.path=path && !seen.has(path) && seen.size<1500?path:null;if(this.path)seen.add(path)},
   onLeave(ret){if(this.path)log('cache_query',{source:name,path:this.path,available:ret.toInt32()!==0})}
  }));
 }
 let albumCells=0;
 keep.push(Interceptor.attach(base.add(0x2fbbcb8),{onEnter(args){
  if(albumCells++>=40)return;
  try{const p=args[1],u=p.add(0x20).readPointer();log('album_cell',{
   visible:p.add(0x10).readU8(),gallery:managed(p.add(0x18).readPointer()),
   unit:u.isNull()?null:managed(u.add(0x18).readPointer()),
   evolution:u.isNull()?null:u.add(0x20).readS32()
  })}catch(e){log('album_diagnostic_error',String(e))}
 }}));
 keep.push(Interceptor.attach(base.add(0x2fbc058),{onEnter(args){log('album_thumbnail',managed(args[1]))}}));
 keep.push(Interceptor.attach(base.add(0x32f0564),{onLeave(ret){log('octo_setup_returned',ret.toInt32())}}));
 log('native_runtime_ready',{strategy:'Verified local asset provider; original startup, tasks, Unity UI and animation logic retained'});
}
rpc.exports={init(){
 log('bootstrap_loaded',{revision:'local-provider-v1'});
 setTimeout(()=>{const poll=setInterval(()=>{
  try{const m=Process.findModuleByName('libil2cpp.so');if(m){clearInterval(poll);install(m)}}
  catch(e){log('runtime_install_error',String(e.stack||e));clearInterval(poll)}
 },100);keep.push(poll)},600);
}};
