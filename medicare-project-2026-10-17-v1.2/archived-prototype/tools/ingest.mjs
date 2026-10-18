import {readFile,writeFile,rename} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
export function validateCatalog(records,manifest){
 if(!manifest||!manifest.source_id||!manifest.source_release||!Number.isInteger(manifest.benefit_year)||!Number.isInteger(manifest.expected_records)||manifest.expected_records<0)throw new Error('Invalid source manifest');
 if(manifest.rights?.ingest!==true)throw new Error('Source has no documented ingestion permission');
 const ids=new Set(),types={},errors=[];
 records.forEach((r,i)=>{
  if(!r||typeof r!=='object')return errors.push(`Row ${i+1}: record must be an object`);
  if(typeof r.plan_version_id!=='string'||!r.plan_version_id||ids.has(r.plan_version_id))errors.push(`Row ${i+1}: missing or duplicate plan_version_id`);ids.add(r.plan_version_id);
  if(r.source_id!==manifest.source_id||r.source_release!==manifest.source_release)errors.push(`Row ${i+1}: source lineage mismatch`);
  if(r.benefit_year!==manifest.benefit_year)errors.push(`Row ${i+1}: wrong benefit year`);
  if(!['ma','mapd','pdp','medigap'].includes(r.plan_type))errors.push(`Row ${i+1}: unsupported plan type`);
  if(!Array.isArray(r.service_area_codes)||!r.service_area_codes.length||r.service_area_codes.some(c=>typeof c!=='string'||!c))errors.push(`Row ${i+1}: missing service area`);
  if(!r.source_record_id)errors.push(`Row ${i+1}: missing source record locator`);
  if(r.monthly_premium_cents!==null&&(!Number.isSafeInteger(r.monthly_premium_cents)||r.monthly_premium_cents<0))errors.push(`Row ${i+1}: premium must be integer cents or null`);
  types[r.plan_type]=(types[r.plan_type]||0)+1;
 });
 if(records.length!==manifest.expected_records)errors.push(`Count mismatch: expected ${manifest.expected_records}, received ${records.length}`);
 return {passed:errors.length===0,records:records.length,unique_plan_versions:ids.size,types,errors,synthetic:manifest.synthetic===true,coverage_claim:'Validated canonical records only. This does not establish source completeness, current quotes, network accuracy or enrollment authority.'};
}
async function main(){
 const [inputPath,manifestPath,outputPath]=process.argv.slice(2);if(!outputPath)throw new Error('Usage: node tools/ingest.mjs canonical.jsonl manifest.json output.json');
 const [raw,manifestText]=await Promise.all([readFile(inputPath,'utf8'),readFile(manifestPath,'utf8')]);
 const records=raw.split(/\r?\n/).filter(x=>x.trim()).map((line,i)=>{try{return JSON.parse(line);}catch{throw new Error(`Invalid JSON at line ${i+1}`);}});
 const manifest=JSON.parse(manifestText),report=validateCatalog(records,manifest);
 if(!report.passed){console.error(JSON.stringify(report,null,2));process.exitCode=1;return;}
 const content=JSON.stringify({manifest,content_hash:createHash('sha256').update(raw).digest('hex'),report,records},null,2);
 const temp=outputPath+`.${process.pid}.tmp`;await writeFile(temp,content,{flag:'wx'});await rename(temp,outputPath);console.log(JSON.stringify(report,null,2));
}
if(process.argv[1]===fileURLToPath(import.meta.url))main().catch(e=>{console.error(e.message);process.exitCode=1;});
