/* Real view modules and continuation helpers; fictional data, no browser/network. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const root=path.join(__dirname,'../web-8894');
class Node {
 constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.attributes={};this.text='';this.className='';this.classList={add(){},remove(){},toggle(){}};}
 set textContent(t){this.text=String(t);this.children=[];}
 get textContent(){return this.text+this.children.map(c=>typeof c==='string'?c:c.textContent).join(' ');}
 append(...v){this.children.push(...v);}
 prepend(...v){this.children.unshift(...v);}
 setAttribute(k,v){this.attributes[k]=v;}
 addEventListener(k,v){this[k]=v;}
}
const all=n=>[n,...n.children.filter(c=>typeof c==='object').flatMap(all)];
function load(){const document={createElement:t=>new Node(t),getElementById:()=>null},window={};
 const ctx={window,document,Intl,Map,Set,Option:function(t,v){const n=new Node('option');n.textContent=t;n.value=v;return n;}};
 for(const name of ['guided-close.js','conversation-checks.js'])vm.runInNewContext(fs.readFileSync(path.join(root,name),'utf8'),ctx);
 return ctx;
}

for(const kind of ['doctor','drug']) test(kind+' selector retains exact staged identity and never submits on selection',()=>{
 const {window}=load(),host=new Node('main');let changed=0;
 const q={kind,field:kind==='doctor'?'doctor':'formulary_product',token:'fiction',question:'Choose the exact listing',choices:Array.from({length:9},(_,i)=>({value:'source-'+i,label:kind==='doctor'?'Fictional Doctor '+i:'Fictional Medicine '+i+' mg oral tablet'}))};
 window.DaylightConversationChecks.render(host,{results:[],question:q},{visit:'fiction.1',changed(){changed++},defer(){},edit(){},editCheck(){}});
 const select=all(host).find(n=>n.tagName==='select');assert.ok(select);assert.equal(select.children.length,10);
 assert.equal(window.DaylightConversationChecks.answer(q),null);
 select.value='3';select.change();assert.equal(changed,1);
 const answer=window.DaylightConversationChecks.answer(q);assert.equal(answer.value,'source-3');assert.equal(answer.token,q.token);
});
