/* Ajuda contextual compartilhada: conteudo original preservado, baloes por clique. */
(() => {
  'use strict';
  const entries=new WeakMap();let serial=0,current=null;
  const statusIds=new Set(['entry-note','msg','market-center','marketmsg','online-message','stores-message','competitors-message','importmsg','center-message','detail-message','detail-online-message','detail-market-message']);
  const names={'entry-note':'Última compra',msg:'Consulta de produtos','market-center':'Centro do raio',marketmsg:'Preços importados','online-message':'Consulta online','stores-message':'Lojas no raio','competitors-message':'Cadastro de concorrentes',importmsg:'Importação','center-message':'Centro da pesquisa','detail-message':'Ficha do produto','detail-online-message':'Preços online do produto','detail-market-message':'Observações do produto'};
  const panel=document.createElement('aside');panel.id='price-help-popover';panel.className='help-popover';panel.hidden=true;panel.setAttribute('popover','manual');panel.setAttribute('role','dialog');panel.setAttribute('aria-labelledby','price-help-title');
  const heading=document.createElement('div');heading.className='help-popover-heading';const title=document.createElement('strong');title.id='price-help-title';const dismiss=document.createElement('button');dismiss.type='button';dismiss.className='help-dismiss';dismiss.textContent='×';dismiss.setAttribute('aria-label','Fechar balão');heading.append(title,dismiss);
  const content=document.createElement('div');content.className='help-popover-content';panel.append(heading,content);document.body.append(panel);
  const announcer=document.createElement('span');announcer.className='visually-hidden';announcer.setAttribute('role','status');announcer.setAttribute('aria-live','polite');document.body.append(announcer);
  function position(){
    if(!current)return;
    const r=current.button.getBoundingClientRect();
    if(!current.node.isConnected||!current.button.getClientRects().length||r.bottom<0||r.top>innerHeight){close(false);return;}
    const width=Math.min(430,innerWidth-24);panel.style.width=width+'px';panel.style.maxHeight=Math.max(120,Math.min(480,innerHeight-32))+'px';
    const h=panel.getBoundingClientRect().height,left=Math.max(12,Math.min(r.left,innerWidth-width-12));
    const above=r.bottom+10+h>innerHeight-12&&r.top>h+10;
    panel.style.left=left+'px';panel.style.top=Math.max(12,Math.min(above?r.top-h-10:r.bottom+10,innerHeight-h-12))+'px';panel.dataset.side=above?'above':'below';panel.style.setProperty('--arrow-x',Math.max(18,Math.min(width-24,r.left+r.width/2-left))+'px');
  }
  function close(restore=true){
    const old=current;if(!old)return;current=null;old.button.setAttribute('aria-expanded','false');
    if(typeof panel.hidePopover==='function'&&panel.matches(':popover-open'))panel.hidePopover();panel.hidden=true;
    if(restore&&old.button.isConnected)old.button.focus({preventScroll:true});
  }
  function fill(entry){
    title.textContent=entry.scope;panel.dataset.kind=entry.kind;content.replaceChildren();
    const clone=entry.node.cloneNode(true);clone.hidden=false;clone.removeAttribute('id');clone.removeAttribute('role');clone.removeAttribute('aria-live');clone.removeAttribute('data-help-content');clone.className='';
    clone.querySelectorAll('[id]').forEach(n=>n.removeAttribute('id'));content.append(clone);position();
  }
  function open(entry){
    if(current===entry){close();return;}close(false);current=entry;
    (entry.button.closest('dialog[open]')||document.body).append(panel);panel.hidden=false;
    if(typeof panel.showPopover==='function')panel.showPopover();
    entry.button.setAttribute('aria-expanded','true');fill(entry);dismiss.focus({preventScroll:true});position();
  }
  function sync(entry){
    const text=entry.node.textContent.trim();entry.anchor.hidden=!text;
    entry.kind=entry.node.dataset.helpKind||(entry.node.classList.contains('error')?'error':entry.node.classList.contains('warning')?'warning':'info');
    entry.scope=entry.node.dataset.helpLabel||names[entry.node.id]||entry.scope;
    const label=entry.kind==='error'?'Erro':entry.kind==='warning'&&['Ajuda','Status'].includes(entry.label)?'Atenção':entry.label;
    const icon=entry.kind==='error'?'!':entry.kind==='warning'?'!':'?';
    if(entry.icon.textContent!==icon)entry.icon.textContent=icon;
    if(entry.caption.textContent!==label)entry.caption.textContent=label;
    entry.button.dataset.kind=entry.kind;entry.button.setAttribute('aria-label',(entry.kind==='error'?'Erro':entry.kind==='warning'?'Aviso':'Informação')+' — '+entry.scope+' — abrir detalhes');entry.button.title=label+' — '+entry.scope;
    entry.node.hidden=true;
    if(current===entry){if(!text)close(false);else fill(entry);}
  }
  function attach(node,options={}){
    if(!node||node.dataset.helpKeep==='true'||node.parentElement?.closest('[data-help-content]')||node.closest('.help-popover,.help-anchor')||node.matches('a,button,input,select,textarea')||node.querySelector('button,input,select,textarea,a[download]'))return;
    if(entries.has(node)){sync(entries.get(node));return;}
    if(node.matches('td.condition-info')){
      node.classList.remove('condition-info');const detail=document.createElement('div');
      detail.dataset.helpLabel=/\bpix\b/i.test(node.textContent)?'Pix':'Condições';
      if(detail.dataset.helpLabel==='Pix')detail.dataset.helpKind='warning';
      while(node.firstChild)detail.append(node.firstChild);node.append(detail);return attach(detail,{scope:'Condições da oferta'});
    }
    const anchor=document.createElement('span');anchor.className='help-anchor';const button=document.createElement('button');button.type='button';button.className='help-trigger';
    const icon=document.createElement('span');icon.className='help-icon';icon.setAttribute('aria-hidden','true');const caption=document.createElement('span');caption.className='help-caption';button.append(icon,caption);anchor.append(button);node.before(anchor);
    const scope=options.scope||node.dataset.helpLabel||names[node.id]||node.closest('.panel,.chart-group,.card,.tab')?.querySelector('h1,h2,h3')?.textContent||'Informações da tela';
    const label=options.label||node.dataset.helpLabel||(statusIds.has(node.id)?'Status':node.classList.contains('condition-info')?'Condições':'Ajuda');
    const entry={node,anchor,button,icon,caption,scope,label,kind:'info'};entries.set(node,entry);node.dataset.helpContent='true';
    button.dataset.helpFor=node.id||'help-'+(++serial);button.setAttribute('aria-expanded','false');button.setAttribute('aria-controls',panel.id);button.setAttribute('aria-haspopup','dialog');
    if(options.compact)button.classList.add('help-compact');
    node.removeAttribute('role');node.removeAttribute('aria-live');
    button.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();open(entry);});sync(entry);
  }
  const selector='.notice,.warning,.error,p.muted,.chart-group > .muted,.condition-info,[data-help-label],[id$="-sources"] > p,'+[...statusIds].map(id=>'#'+id).join(',');
  function scan(root){
    if(root.nodeType!==1||root.closest('.help-popover,.help-anchor,[data-help-content]'))return;
    if(root.matches(selector))attach(root);
    root.querySelectorAll(selector).forEach(node=>attach(node));
  }
  // Textos fixos de orientacao; dados, campos e acoes continuam na tela.
  document.querySelectorAll('#tab-integracao .panel').forEach(box=>{const group=document.createElement('div');group.dataset.helpLabel='Orientações';[...box.children].filter(child=>!child.matches('h1,h2,h3')).forEach(child=>group.append(child));box.append(group);attach(group,{scope:box.querySelector('h2')?.textContent});});
  document.querySelectorAll('.tab > p:not([id]),.panel > p:not([id]),.heading > div > .muted,#product-dialog .panel > p:not([id])').forEach(node=>attach(node));
  document.querySelectorAll('.card small').forEach(node=>attach(node,{scope:node.closest('.card').querySelector('span')?.textContent,compact:true}));
  scan(document.body);
  const observer=new MutationObserver(records=>{
    const changed=new Set();
    records.forEach(record=>{
      const target=record.target.nodeType===1?record.target:record.target.parentElement;
      if(!target||target.closest('.help-popover,.help-anchor'))return;
      const original=target.closest('[data-help-content]');if(original&&entries.has(original))changed.add(entries.get(original));
      record.addedNodes.forEach(node=>scan(node));
    });
    changed.forEach(entry=>sync(entry));if(current&&!current.button.isConnected)close(false);
  });
  observer.observe(document.body,{childList:true,subtree:true,characterData:true});
  dismiss.addEventListener('click',()=>close());
  document.addEventListener('click',event=>{if(current&&!panel.contains(event.target))close(false);});
  document.addEventListener('keydown',event=>{if(current&&event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();close();}},true);
  document.addEventListener('close',event=>{if(current&&event.target.contains(current.button))close(false);},true);
  window.addEventListener('resize',position);document.addEventListener('scroll',position,true);
  window.PriceHelp={attach,close,refresh:()=>scan(document.body),message(id,text,error=false){
    const node=document.getElementById(id);node.textContent=text;node.className=error?'error':'muted';attach(node);
    if(error){(node.closest('dialog[open]')||document.body).append(announcer);announcer.textContent=(names[id]||'Atenção')+': '+text.slice(0,240);}
  }};
})();
