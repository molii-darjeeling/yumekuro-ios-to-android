/* Local asset delivery backend for the preserved Unity client.
 * No startup task, error, signature or content check is forced to succeed.
 * Locations and dependency lists come from the verified local snapshot.
 */
function installLocalProvider(module, log, retained) {
 const base=module.base, nil=ptr(0);
 const LOCAL='/data/user/0/com.yumekuro.local/files/offline/';
 const snapshot=JSON.parse(File.readAllText(LOCAL+'local-snapshot.json'));
 if(snapshot.format!==1 || !snapshot.complete)throw new Error('Local snapshot is not complete');
 for(const filename of ['metadata-supplement.json','audio-supplement.json','cuesheet-supplement.json','visual-supplement.json','raw-supplement.json','play-assets-supplement.json']){
  const supplement=JSON.parse(File.readAllText(LOCAL+filename));
  if(supplement.format!==1)throw new Error('Invalid local supplement: '+filename);
  snapshot.files.push(...supplement.files);
 }
 // The authoritative Play resource wins over an earlier source adaptation.
 snapshot.files=[...new Map(snapshot.files.map(row=>[row[0],row])).values()];
 const api=(n,r,a)=>new NativeFunction(module.getExportByName('il2cpp_'+n),r,a);
 const domain=api('domain_get','pointer',[])();
 if(api('thread_current','pointer',[])().isNull())api('thread_attach','pointer',['pointer'])(domain);
 const count=Memory.alloc(8);count.writeU64(0);
 const assemblies=api('domain_get_assemblies','pointer',['pointer','pointer'])(domain,count);
 const imageOf=api('assembly_get_image','pointer',['pointer']);
 const find=api('class_from_name','pointer',['pointer','pointer','pointer']);
 function cls(ns,name){
  for(let i=0;i<count.readU64().toNumber();i++){
   const k=find(imageOf(assemblies.add(i*8).readPointer()),Memory.allocUtf8String(ns),Memory.allocUtf8String(name));
   if(!k.isNull())return k;
  }
  throw new Error('Managed class missing: '+ns+'.'+name);
 }
 const allocate=api('object_new','pointer',['pointer']);
 const newString=api('string_new','pointer',['pointer']);
 const string=value=>newString(Memory.allocUtf8String(value));
 const store=api('gc_wbarrier_set_field','void',['pointer','pointer','pointer']);
 const pin=api('gchandle_new','uint',['pointer','bool']);
 const handles=[];retained.push(handles);
 const hold=value=>{handles.push(pin(value,0));return value};
 const writeRef=(obj,offset,value)=>store(obj,obj.add(offset),value);
 const fieldOf=api('class_get_field_from_name','pointer',['pointer','pointer']);
 const getStatic=api('field_static_get_value','void',['pointer','pointer']);
 const setStatic=api('field_static_set_value','void',['pointer','pointer']);
 const managerClass=cls('Vita2.StandAlone','Vita2PlayAssetDeliveryManager');
 const packNamesField=fieldOf(managerClass,Memory.allocUtf8String('AssetPackNames'));
 const temp=Memory.alloc(8);getStatic(packNamesField,temp);
 const originalNames=temp.readPointer();
 if(originalNames.isNull())throw new Error('Asset delivery class has not initialized');
 const listClass=originalNames.readPointer();
 const methodOf=api('class_get_method_from_name','pointer',['pointer','pointer','int']);
 const ctorInfo=methodOf(listClass,Memory.allocUtf8String('.ctor'),0);
 const addInfo=methodOf(listClass,Memory.allocUtf8String('Add'),1);
 const constructList=new NativeFunction(ctorInfo.readPointer(),'void',['pointer','pointer']);
 const addString=new NativeFunction(addInfo.readPointer(),'void',['pointer','pointer','pointer']);
 function stringList(values){
  const list=hold(allocate(listClass));constructList(list,ctorInfo);
  for(const value of values)addString(list,string(value),addInfo);
  if(list.add(0x18).readS32()!==values.length)throw new Error('Managed list construction failed');
  return list;
 }
 const packClass=cls('Google.Play.AssetDelivery.Internal','AssetPackLocation');
 const locationClass=cls('Google.Play.AssetDelivery.Internal','AssetLocationImpl');
 const replaceName=new NativeFunction(base.add(0x308bc5c),['pointer','pointer'],['pointer','pointer']);
 const index=new Map(),byId=new Map(),byIdentity=new Map(),packs=new Map(),locations=new Map(),dependencyLists=new Map();
 function text(p){return p.isNull()?null:p.add(20).readUtf16String(p.add(16).readS32())}
 function keyFor(name){const pair=replaceName(string(name),nil);return [text(pair[0]),text(pair[1])]}
 for(const row of snapshot.files){
  byIdentity.set(String(row[1])+'|'+row[0],row);
  if(row[5] && row[5].kind==='raw'){
   if(!/^R[0-9]+\.(?:mp4|mov|mp3|caf|wav)$/.test(row[5].file))throw new Error('Invalid raw resource file');
   continue; // Raw Octo R items are not PAD AssetBundles or A-item IDs.
  }
  const [pack,path]=keyFor(row[0]);
  const key=pack+'/'+path;
  if(index.has(key) && index.get(key)[1]!==row[1])throw new Error('Resource name collision: '+key);
  index.set(key,row);byId.set(String(row[1]),row);
  if(!packs.has(pack))packs.set(pack,[]);
  packs.get(pack).push(row);
 }
 // This build's preload catalogue describes its actual local packs, rather
 // than Google Play's unrelated installation catalogue.
 const catalogue=stringList([...packs.keys()].sort());
 setStatic(packNamesField,catalogue);
 getStatic(packNamesField,temp);
 if(!temp.readPointer().equals(catalogue))throw new Error('Local catalogue reference did not round-trip through the managed API');
 const makePack=pack=>{
  if(!packs.has(pack))return nil;
  if(!locations.has('pack:'+pack)){
   const obj=hold(allocate(packClass));
   writeRef(obj,0x10,string(LOCAL+'payload'));
   obj.add(0x18).writeS32(0); // Real files, not APK offsets.
   locations.set('pack:'+pack,obj);
  }
  return locations.get('pack:'+pack);
 };
 function findRow(pack,path){
  path=path.replace(/^assetpack\//,'');
  let row=index.get(pack+'/'+path);
  if(!row)row=index.get(pack+'/'+path.replace(/\.(?:assetbundle|unity3d|bundle|ab)$/,''));
  return row;
 }
 function payloadPath(row){return LOCAL+'payload/'+(row[5] && row[5].kind==='raw'?row[5].file:row[1])}
 function validFile(row){
  try{const f=new File(payloadPath(row),'rb');f.seek(0,2);const length=f.tell();f.close();return length===row[2]}catch(_){return false}
 }
 function makeLocation(pack,path){
  const row=findRow(pack,path);
  if(!row || !validFile(row)){log('local_asset_missing',{pack,path,reason:row?'file_missing_or_incomplete':'not_in_verified_snapshot'});return nil}
  const cacheKey='file:'+row[1];
  if(!locations.has(cacheKey)){
   const obj=hold(allocate(locationClass));
   writeRef(obj,0x10,string(payloadPath(row)));
   obj.add(0x18).writeU64(0);obj.add(0x20).writeU64(row[2]);
   locations.set(cacheKey,obj);
   log('local_asset_location',{name:row[0],id:row[1],bytes:row[2],dependencies:row[4].length});
  }
  return locations.get(cacheKey);
 }
 function replace(rva,ret,args,fn){const callback=new NativeCallback(fn,ret,args);retained.push(callback);Interceptor.replace(base.add(rva),callback)}
 // Legacy Octo and PAD share the same verified physical files. Reporting a
 // cache hit requires an actual matching item and a complete local file;
 // Unity's original file loader still performs the real AssetBundle load.
 function octoRow(item){
  if(item.isNull())return null;
  const row=byIdentity.get(String(item.add(0x10).readS32())+'|'+text(item.add(0x18).readPointer()));
  return row && row[0]===text(item.add(0x18).readPointer()) && validFile(row)?row:null;
 }
 const logicalRows=new Map(snapshot.files.map(row=>[row[0],row]));
 const incompleteReported=new Set();
 function locallyComplete(row,rootName){
  const seen=new Set(),missing=[];
  function visit(current,name){
   if(!current || !validFile(current)){missing.push(name);return false}
   if(seen.has(current[0]))return true;
   seen.add(current[0]);
   let complete=true;
   for(const dependency of current[4]){
    if(!visit(logicalRows.get(dependency),dependency))complete=false;
   }
   return complete;
  }
  const name=rootName || (row?row[0]:'unknown');
  const complete=visit(row,name);
  if(!complete && !incompleteReported.has(name) && incompleteReported.size<500){
   incompleteReported.add(name);
   log('local_asset_incomplete',{name,missing:missing.slice(0,16),missingCount:missing.length});
  }
  return complete;
 }
 // Availability queries do not go through IOctoCaching.IsCached: the
 // original concrete implementation calls its old storage index directly.
 // Resolve both implementations against the same real local asset files.
 for(const rva of [0x46b5d08,0x46bbc78,0x46b5efc,0x46bbe30]){
  replace(rva,'bool',['pointer','pointer','pointer'],(_self,item)=>
   locallyComplete(octoRow(item),item.isNull()?'unknown':text(item.add(0x18).readPointer()))?1:0);
 }
 // Choose the original static renderer only when this exact card's full
 // static asset is complete and its animation dependency closure is not.
 // Complete animations keep their original route and unlock requirements.
 // No thumbnail substitution or change to the player's unlock save is used.
 function staticCardFallback(unit){
  if(unit.isNull())return false;
  const kind=unit.add(0x10).readS32(),id=text(unit.add(0x18).readPointer());
  let type,suffix;
  if(kind===0){
   type='meister';
   suffix=({1:'sun',2:'mon',4:'pur'})[unit.add(0x20).readS32()];
  }else if(kind===1 && unit.add(0x24).readS32()===1){
   type='fairy';suffix='evo';
  }
  if(!suffix || !id)return false;
  const staticName='unit/'+type+'/cardimage/'+id+'_card_'+suffix;
  const liveName='unit/'+type+'/livecardimage/'+id+'_livecard_'+suffix;
  const still=logicalRows.get(staticName);
  return !!still && locallyComplete(still) && !locallyComplete(logicalRows.get(liveName),liveName);
 }
 const staticCardReady=new NativeFunction(base.add(0x3089194),'bool',['pointer','pointer']);
 const displayReadyAddress=base.add(0x3089380);
 let originalDisplayReady;
 const displayReadyCallback=new NativeCallback((unit,both,info)=>
  staticCardFallback(unit)?staticCardReady(unit,nil):originalDisplayReady(unit,both,info),
  'bool',['pointer','bool','pointer']);
 retained.push(displayReadyCallback);
 originalDisplayReady=new NativeFunction(Interceptor.replaceFast(displayReadyAddress,displayReadyCallback),
  'bool',['pointer','bool','pointer']);
 // Both native methods return the same genuine UniTask (source + token),
 // and take identical cancellation/anchor arguments. Never create or mark
 // a task as successful: return the original static loader's actual task.
 const cardArgs=['pointer','pointer','pointer','int','pointer'];
 const cardTask=['pointer','uint64'];
 const loadStaticCard=new NativeFunction(base.add(0x380c3f8),cardTask,cardArgs);
 let originalLoadLiveCard;
 const loadCardCallback=new NativeCallback((self,unit,cancellation,anchor,info)=>{
  if(staticCardFallback(unit)){
   const kind=unit.add(0x10).readS32();
   log('static_card_fallback',{unit:text(unit.add(0x18).readPointer()),characterType:kind,
    evolution:unit.add(kind===1?0x24:0x20).readS32(),renderer:'UICardContainer.LoadCard'});
   return loadStaticCard(self,unit,cancellation,anchor,nil);
  }
  return originalLoadLiveCard(self,unit,cancellation,anchor,info);
 },cardTask,cardArgs);
 retained.push(loadCardCallback);
 originalLoadLiveCard=new NativeFunction(Interceptor.replaceFast(base.add(0x380c6a8),loadCardCallback),cardTask,cardArgs);
 const octoPaths=new Map();
 for(const rva of [0x46b687c,0x46bc2b0]){
  replace(rva,'uint',['pointer','pointer','pointer','pointer','pointer'],(_self,_bucket,_file,item)=>octoRow(item)?3:0);
 }
 for(const rva of [0x46b6970,0x46bc2c8]){
  replace(rva,'pointer',['pointer','pointer','pointer','pointer','pointer'],(_self,_bucket,_file,item)=>{
   const row=octoRow(item);if(!row)return nil;
   if(!octoPaths.has(row[0])){
    octoPaths.set(row[0],hold(string(payloadPath(row))));
    log('local_octo_path',{name:row[0],id:row[1]});
   }
   return octoPaths.get(row[0]);
  });
 }
 for(const rva of [0x46b6844,0x46bc2a8]){
  replace(rva,'bool',['pointer','pointer','pointer','pointer'],()=>0); // Files are private storage, never APK-embedded.
 }
 // A pure local backend has no network fallback. A missing resource is a
 // normal failed download callback, not an Android permission exception and
 // never a fabricated successful task.
 const errorClass=cls('Octo','NamedError');
 const errorCtor=new NativeFunction(base.add(0x32e7484),'void',['pointer','pointer','pointer','pointer','pointer']);
 const invoke=api('runtime_invoke','pointer',['pointer','pointer','pointer','pointer']);
 replace(0x46a79e8,'void',['pointer','pointer','pointer','pointer','pointer','pointer'],(_self,item,_path,complete)=>{
  const name=item.isNull()?'unknown':text(item.add(0x18).readPointer());
  log('local_octo_missing',{name,networkAttempted:false});
  if(complete.isNull())return;
  const error=allocate(errorClass);
  errorCtor(error,string(name),string('local.resource.unavailable'),string('Resource is absent from the verified local snapshot: '+name),nil);
  const method=methodOf(complete.readPointer(),Memory.allocUtf8String('Invoke'),1);
  if(method.isNull())throw new Error('Download failure callback method is unavailable');
  const args=Memory.alloc(8);args.writePointer(error);
  const exception=Memory.alloc(8);exception.writePointer(nil);
  invoke(method,complete,args,exception);
  if(!exception.readPointer().isNull())log('local_download_callback_exception',name);
 });
 replace(0x616ad18,'pointer',['pointer','pointer','pointer'],(_self,name)=>makePack(text(name)));
 // Local snapshots are immutable. Readiness is tied to this snapshot's
 // catalogue; asking for a newer Play version is not a network operation.
 replace(0x616e7e0,'bool',['pointer','pointer','bool','pointer'],(_self,name,_newer)=>packs.has(text(name))?1:0);
 const packAvailable=new NativeFunction(base.add(0x616dca8),'void',['pointer','pointer']);
 const packError=new NativeFunction(base.add(0x616eb30),'void',['pointer','int','pointer']);
 replace(0x616e5c4,'void',['pointer','pointer','bool','pointer'],(_self,request,_available)=>{
  const name=text(request.add(0x28).readPointer());
  if(packs.has(name))packAvailable(request,nil);
  else{log('local_pack_missing',{name,error:'BundleUnavailable',networkAttempted:false});packError(request,2,nil)}
 });
 replace(0x616ae44,'pointer',['pointer','pointer','pointer','pointer'],(_self,pack,path)=>{
  try{return makeLocation(text(pack),text(path))}catch(e){log('local_location_error',String(e));return nil}
 });
 // PAD manifests are build artefacts absent from the iPad export. The Octo
 // database already contains the original Android dependency graph, so
 // return that graph as the same List<string> contract the caller expects.
 replace(0x308a6bc,'pointer',['pointer','pointer'],path=>{
  const full=text(path),id=full.substring(full.lastIndexOf('/')+1).replace(/\.manifest$/,'');
  const row=byId.get(id);
  if(!row){log('local_dependency_manifest_missing',full);return nil}
  if(!dependencyLists.has(id))dependencyLists.set(id,stringList(row[4]));
  return dependencyLists.get(id);
 });
 log('local_provider_ready',{assets:index.size,packs:[...packs.keys()].sort(),bytes:snapshot.bytes});
 return {assets:index.size,packs:packs.size};
}
