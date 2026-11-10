class E {
  constructor(tag='div'){
    this.tagName=tag;this.children=[];this.dataset={};this.disabled=false;
    this.events={};this.attributes={};this.value='';this.text='';this.textWrites=0;this.insertions=0;
  }
  get textContent(){return this.text+this.children.map(child=>child.textContent).join('');}
  set textContent(value){this.text=String(value);this.textWrites++;this.children=[];}
  get cells(){return this.children;}
  get firstElementChild(){return this.children[0]??null;}
  get nextElementSibling(){
    if(!this.parentNode)return null;
    const siblings=this.parentNode.children;
    return siblings[siblings.indexOf(this)+1]??null;
  }
  append(...items){
    for(const item of items){
      if(item.tagName==='fragment')this.append(...item.children);
      else this.insertBefore(item,null);
    }
  }
  insertBefore(child,before){
    if(child===before)return;
    child.remove();
    const position=before===null?this.children.length:this.children.indexOf(before);
    if(position<0)throw Error('insertBefore: reference is not a child');
    child.parentNode=this;
    this.children.splice(position,0,child);
    this.insertions++;
  }
  replaceChildren(...items){for(const child of [...this.children])child.remove();this.text='';this.append(...items);}
  remove(){
    if(!this.parentNode)return;
    const siblings=this.parentNode.children;
    siblings.splice(siblings.indexOf(this),1);
    this.parentNode=null;
  }
  addEventListener(event,fn){this.events[event]=fn;}
  setAttribute(name,value){this.attributes[name]=String(value);}
  getAttribute(name){return this.attributes[name]??null;}
  querySelector(selector){return this.map?.[selector]??null;}
}
module.exports={E};
