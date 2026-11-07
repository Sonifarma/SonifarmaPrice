const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {PGlite} = require(process.env.PGLITE_MODULE || '../work/sql-fixture/node_modules/@electric-sql/pglite');
const py = process.env.PYTHON_EXECUTABLE || '.venv/bin/python';
const source = `
import json,os
os.environ['MODE']='demo'
os.environ['A7_UNIT']='1'
from datetime import date
from decimal import Decimal
from app.main import SQL
from app.product_review import build_query
from app.market_products import lookup_query
config=dict(SCHEMA='public',TABLE='entrada_teste',ID_COLUMN='embalagemid',UNIT_COLUMN='unidadeid',DATE_COLUMN='datahora',STATUS_COLUMN='status',STATUS_VALUE='F',ID_KIND='embalagem')
cases={}
for name,cfg,kind,only,start,end,limit,offset,q in [
 ('review',None,None,True,None,None,100,0,''),
 ('entry_first',config,'timestamp without time zone',False,date(2026,11,6),date(2026,11,7),1,0,''),
 ('entry_second',config,'timestamp without time zone',False,date(2026,11,6),date(2026,11,7),1,1,''),
 ('timezone',dict(config,TABLE='entrada_tz'),'timestamp with time zone',False,date(2026,11,7),date(2026,11,7),100,0,''),
 ('injection',None,None,False,None,None,100,0,"';DROP TABLE produto;--"),
]:
 query,params=build_query(SQL,cfg,kind,'produto',q,start,end,Decimal('30'),only,False,limit,offset)
 cases[name]={'query':query,'params':params}
for name,term in [('lookup_middle','uto'),('lookup_ean','4006381333931'),('lookup_literal','%_')]:
 query,params=lookup_query(term,20,0)
 cases[name]={'query':query,'params':params}
print(json.dumps(cases,default=str))
`;
(async()=>{
 const cases=JSON.parse(execFileSync(py,['-c',source],{encoding:'utf8'}));
 const db=new PGlite();
 try {
  await db.exec(`
   CREATE TABLE produto(id int PRIMARY KEY,codigo text,descricao text,status text);
   CREATE TABLE embalagem(id int PRIMARY KEY,produtoid int,codigobarras text,descricao text,quantidadeporembalagem numeric,precovenda numeric);
   CREATE TABLE custoproduto(id int,produtoid int,unidadenegocioid int,custo numeric,customedio numeric);
   CREATE TABLE estoque(id int,embalagemid int,unidadenegocioid int,estoque numeric);
   CREATE TABLE venda(id int,unidadenegocioid int,status text,datahorafechamento timestamp);
   CREATE TABLE itemvenda(vendaid int,embalagemid int,unidadenegocioid int,status text,quantidade numeric,valortotal numeric);
   CREATE TABLE entrada_teste(embalagemid int,unidadeid int,status text,datahora timestamp);
   INSERT INTO produto VALUES(1,'001','Produto A','A'),(2,'002','B','A'),(3,'003','C','A'),(4,'004','D','A');
   INSERT INTO embalagem VALUES(11,1,'4006381333931','UN',1,10),(12,1,'96385074','CX',2,20),(22,2,'04006381333931','UN',1,10),(33,3,'12345678','UN',1,0),(44,4,'12345679','UN',1,10);
   INSERT INTO custoproduto VALUES(1,1,1,8,8),(99,1,2,999,999),(2,2,1,4,4),(3,3,1,5,5),(4,4,1,'NaN',1);
   INSERT INTO estoque VALUES(1,11,1,5),(99,11,2,999);
   INSERT INTO entrada_teste VALUES(11,1,'F','2026-11-07 23:59:59'),(11,2,'F','2026-11-09'),(11,1,'P','2026-11-08'),(22,1,'F','2026-11-06'),(22,1,'F','2026-11-08'),(33,1,'F','2026-11-06 12:00:00');
   CREATE TABLE entrada_tz AS SELECT embalagemid,unidadeid,status,datahora AT TIME ZONE 'America/Sao_Paulo' AS datahora FROM entrada_teste;
   SET default_transaction_read_only=on;
  `);
  async function run(name) {let index=0;return (await db.query(cases[name].query.replace(/%s/g,()=>'$'+(++index)),cases[name].params)).rows;}
  const rows=await run('review');
  assert.deepEqual(rows.map(r=>r.embalagem_id).sort((a,b)=>a-b),[11,33,44]);
  assert.equal(Number(rows.find(r=>r.embalagem_id===11).custo),8);
  assert.equal(Number(rows.find(r=>r.embalagem_id===11).estoque),5);
  const first=await run('entry_first');
  assert.equal(first[0].embalagem_id,11);assert.equal(Number(first[0].total_filtrado),2);
  assert.equal(first.length,2); // limit+1 para informar proxima pagina.
  const second=await run('entry_second');assert.equal(second[0].embalagem_id,33);
  const zoned=await run('timezone');assert.deepEqual(zoned.map(r=>r.embalagem_id),[11]);
  assert.deepEqual(await run('injection'),[]);
  assert.equal((await run('lookup_middle'))[0].produto_id,1);
  assert.equal((await run('lookup_ean'))[0].ean,'4006381333931');
  assert.deepEqual(await run('lookup_literal'),[]);
  console.log('PostgreSQL simulado OK: unidade, status finalizado, ultima entrada, dia completo, fuso, margem/NaN e paginacao antes do limite.');
 } finally {await db.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
