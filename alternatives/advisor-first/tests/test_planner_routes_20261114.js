// Execute the actual workspace open() with UI-only stubs; no HTTP or model.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(__dirname + '/../web-8894/plans-workspace.js', 'utf8');
const begin = source.indexOf('  async function open(handoff');
const end = source.indexOf('  function close(', begin);
const node = () => ({classList: {add(){}, toggle(){}}, setAttribute(){}, replaceChildren(){}, append(){}});
async function route(profile, target) {
  const scope = {window:{},prof:()=>profile,enroll:()=>true,loadLocal(){},loadSeen(){},activate(){},noteStep(){},
    pathView:()=> 'ab', $:node, document:{body:node()},drawer:()=>false,el:node,refresh:async()=>{},scrollTo(){},data:{}};
  vm.createContext(scope);
  await vm.runInContext(source.slice(begin,end)+'\nopen(null, '+JSON.stringify(target || null)+')',scope);
  return scope.view;
}
(async()=>{
  for(const view of ['part-d','advantage','supplement','paths']) {
    assert.equal(await route({conversationPlanner:{plans_view:view},task:'medigap'}),view);
  }
  assert.equal(await route({conversationPlanner:{plans_view:'paths'}},'part-d'),'part-d');
  // Old running backend does not yet emit plans_view: keep its existing route.
  assert.equal(await route({conversationPlanner:{},task:'medigap'}),'ab');
  assert.equal(await route({task:'medigap'}),'ab');
  console.log('7 actual workspace route assertions passed. No HTTP or model calls.');
})().catch(error=>{console.error(error);process.exitCode=1;});
