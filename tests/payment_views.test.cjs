const{test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync('stylist/static/closet-app/payment-views.js','utf8'),ctx);
for(const live of [false,true])test(`dialogue omits single-request quote (live=${live})`,()=>{
 const html=ctx.PaymentViews.render({view:'letter',scene:'agent',live,availablePoints:0,catalog:{points:{status:'ready',data:[]}}});
 assert(!html.includes('本次费用'));assert(!html.includes('以最新报价为准'));assert(html.includes('balance--single'));assert(html.includes('当前可用积分'));assert(html.includes('先留着，稍后再聊'));assert(html.includes('data-action="points"'));
});
for(const value of [0,12.5,null])test(`dialogue balance retains real or unknown state (${value})`,()=>{
 const html=ctx.PaymentViews.render({view:'letter',scene:'agent',live:true,availablePoints:value});
 assert(html.includes(value===null?'以账户查询为准':`<strong>${value}<em>积分</em></strong>`));
});
for(const scene of ['tryon','twin','beautify'])test(`${scene} retains its quote`,()=>{
 const html=ctx.PaymentViews.render({view:'points',scene,live:true,pointsCost:100,availablePoints:20});
 assert(html.includes('本次费用'));assert(html.includes('<strong>100<em>积分</em></strong>'));assert(!html.includes('balance--single'));
});
